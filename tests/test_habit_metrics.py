import unittest

from app.services.habit_metrics import merge_habit_metrics


def make_match(team_id: int = 100) -> dict:
    participants = []
    for pid in range(1, 11):
        participants.append(
            {
                "participantId": pid,
                "puuid": f"puuid-{pid}",
                "teamId": 100 if pid <= 5 else 200,
                "championName": f"Champ{pid}",
                "teamPosition": "MIDDLE",
                "win": pid <= 5,
                "challenges": {"survivedSingleDigitHpCount": 1 if pid == 1 else 0},
            }
        )
    return {"info": {"participants": participants, "teams": [{"teamId": 100, "win": True}, {"teamId": 200, "win": False}]}}


def make_feature(
    minute: int,
    current_gold: dict[int, int] | None = None,
    positions: dict[int, tuple[int, int]] | None = None,
    damage: dict[int, int] | None = None,
) -> dict:
    participant_frames = {}
    for pid in range(1, 11):
        frame: dict = {}
        if current_gold and pid in current_gold:
            frame["currentGold"] = current_gold[pid]
        else:
            frame["currentGold"] = 500
        if positions and pid in positions:
            frame["position"] = {"x": positions[pid][0], "y": positions[pid][1]}
        if damage is not None:
            frame["damageStats"] = {"totalDamageDoneToChampions": damage.get(pid, 0)}
        participant_frames[str(pid)] = frame
    return {
        "match_id": "KR_1",
        "minute": minute,
        "timestamp_ms": minute * 60_000,
        "gold_diff": 0,
        "raw_frame": {"participantFrames": participant_frames},
    }


def make_kill(timestamp_ms: int, killer: int, victim: int, x: int = 7500, y: int = 7500, **extra) -> dict:
    return {
        "type": "CHAMPION_KILL",
        "timestamp": timestamp_ms,
        "killerId": killer,
        "victimId": victim,
        "position": {"x": x, "y": y},
        **extra,
    }


def make_timeline(events: list[dict]) -> dict:
    return {"info": {"frames": [{"timestamp": 0, "events": events}]}}


def base_analysis(puuid: str = "puuid-1") -> dict:
    return {
        "match_id": "KR_1",
        "player": {"puuid": puuid, "champion": "Champ1", "role": "MIDDLE", "team": "blue", "win": True},
        "scores": {},
        "evidence": [],
    }


class GoldRetentionTest(unittest.TestCase):
    def test_rich_streak_and_wallet_death_raise_score(self) -> None:
        features = [
            make_feature(m, current_gold={1: 2200 if 5 <= m <= 9 else 400})
            for m in range(0, 20)
        ]
        timeline = make_timeline([make_kill(7 * 60_000, killer=6, victim=1)])

        analysis = merge_habit_metrics(base_analysis(), make_match(), timeline, features)
        score = analysis["scores"]["gold_retention_score"]

        self.assertIsNotNone(score["value"])
        self.assertGreater(score["value"], 30)  # 5-minute streak (35) + wallet death (12)
        self.assertEqual(score["direction"], "higher_is_worse")
        kinds = [e["type"] for e in analysis["evidence"]]
        self.assertIn("gold_retention", kinds)

    def test_healthy_spending_scores_zero(self) -> None:
        features = [make_feature(m, current_gold={1: 600}) for m in range(0, 20)]
        analysis = merge_habit_metrics(base_analysis(), make_match(), make_timeline([]), features)

        self.assertEqual(analysis["scores"]["gold_retention_score"]["value"], 0)


class GamblerIndexTest(unittest.TestCase):
    def test_shutdown_and_isolated_death_raise_score(self) -> None:
        # Allies grouped bot-side, player dies alone top-side, conceding a shutdown.
        positions = {pid: (11_000, 2_000) for pid in range(2, 6)}
        features = [make_feature(m, positions=positions) for m in range(0, 25)]
        death = make_kill(12 * 60_000, killer=6, victim=1, x=2_000, y=12_000, shutdownBounty=300)

        analysis = merge_habit_metrics(base_analysis(), make_match(), make_timeline([death]), features)
        score = analysis["scores"]["gambler_index"]

        self.assertGreaterEqual(score["value"], 24)  # shutdown (>=13) + isolation (12)
        titles = [e["title"] for e in analysis["evidence"] if e["type"] == "gambler"]
        self.assertTrue(any("Shutdown" in t for t in titles))
        self.assertTrue(any("Isolated" in t for t in titles))

    def test_deep_kills_count_as_aggression(self) -> None:
        features = [make_feature(m) for m in range(0, 25)]
        # Blue player killing deep in red territory (x+y far above the midline).
        kills = [make_kill(10 * 60_000 + i, killer=1, victim=6 + i, x=12_000, y=12_000) for i in range(3)]

        analysis = merge_habit_metrics(base_analysis(), make_match(), make_timeline(kills), features)
        score = analysis["scores"]["gambler_index"]

        self.assertGreaterEqual(score["value"], 12)
        titles = [e["title"] for e in analysis["evidence"] if e["type"] == "gambler"]
        self.assertTrue(any("Aggressive kills" in t for t in titles))

    def test_quiet_game_scores_zero_with_neutral_evidence(self) -> None:
        features = [make_feature(m) for m in range(0, 25)]
        analysis = merge_habit_metrics(base_analysis(), make_match(), make_timeline([]), features)

        self.assertEqual(analysis["scores"]["gambler_index"]["value"], 0)


class TeamfightPersistenceTest(unittest.TestCase):
    def _fight_events(self, player_dies: bool) -> list[dict]:
        ts = 20 * 60_000
        events = [
            make_kill(ts, killer=1, victim=6, assistingParticipantIds=[2, 3]),
            make_kill(ts + 5_000, killer=2, victim=7, assistingParticipantIds=[1]),
            make_kill(ts + 10_000, killer=8, victim=3 if not player_dies else 1, assistingParticipantIds=[9]),
        ]
        return events

    def _damage_features(self) -> list[dict]:
        # Before-fight frame at 19min, after-fight frame at 21min.
        features = []
        for minute in range(0, 30):
            damage = {pid: 1000 * minute for pid in range(1, 11)}
            if minute >= 21:
                damage[1] = 1000 * minute + 3000  # player spikes 3k during the fight
            features.append(make_feature(minute, damage=damage))
        return features

    def test_survived_fight_with_damage_share_scores_above_base(self) -> None:
        analysis = merge_habit_metrics(
            base_analysis(), make_match(), make_timeline(self._fight_events(player_dies=False)), self._damage_features()
        )
        score = analysis["scores"]["teamfight_persistence_score"]

        self.assertIsNotNone(score["value"])
        self.assertGreater(score["value"], 50)
        self.assertEqual(score["direction"], "higher_is_better")

    def test_dying_in_fight_scores_below_survival(self) -> None:
        survived = merge_habit_metrics(
            base_analysis(), make_match(), make_timeline(self._fight_events(player_dies=False)), self._damage_features()
        )["scores"]["teamfight_persistence_score"]["value"]
        died = merge_habit_metrics(
            base_analysis(), make_match(), make_timeline(self._fight_events(player_dies=True)), self._damage_features()
        )["scores"]["teamfight_persistence_score"]["value"]

        self.assertLess(died, survived)

    def test_no_fights_yields_null_score(self) -> None:
        features = [make_feature(m) for m in range(0, 30)]
        analysis = merge_habit_metrics(base_analysis(), make_match(), make_timeline([]), features)

        self.assertIsNone(analysis["scores"]["teamfight_persistence_score"]["value"])


class DeathAccelerationTest(unittest.TestCase):
    def test_chained_deaths_raise_index(self) -> None:
        deaths = [
            make_kill(10 * 60_000, killer=6, victim=1),
            make_kill(12 * 60_000, killer=7, victim=1),
            make_kill(14 * 60_000, killer=8, victim=1),
        ]
        features = [make_feature(m) for m in range(0, 30)]

        analysis = merge_habit_metrics(base_analysis(), make_match(), make_timeline(deaths), features)
        score = analysis["scores"]["death_acceleration_index"]

        self.assertEqual(score["value"], 12 * 2 + 6)  # 3-death chain
        self.assertEqual(score["confidence"], "high")

    def test_spread_out_deaths_score_zero(self) -> None:
        deaths = [
            make_kill(5 * 60_000, killer=6, victim=1),
            make_kill(15 * 60_000, killer=7, victim=1),
            make_kill(25 * 60_000, killer=8, victim=1),
        ]
        features = [make_feature(m) for m in range(0, 30)]

        analysis = merge_habit_metrics(base_analysis(), make_match(), make_timeline(deaths), features)

        self.assertEqual(analysis["scores"]["death_acceleration_index"]["value"], 0)


class MergeBehaviorTest(unittest.TestCase):
    def test_merge_preserves_existing_scores_and_caps_evidence(self) -> None:
        analysis = base_analysis()
        analysis["scores"]["death_cost_index"] = {"value": 10, "confidence": "medium", "direction": "higher_is_worse"}
        analysis["evidence"] = [
            {"minute": m, "type": "death_cost", "title": f"t{m}", "description": "d", "confidence": "medium"}
            for m in range(12)
        ]
        features = [make_feature(m) for m in range(0, 30)]

        merged = merge_habit_metrics(analysis, make_match(), make_timeline([]), features)

        self.assertIn("death_cost_index", merged["scores"])
        self.assertIn("gold_retention_score", merged["scores"])
        self.assertLessEqual(len(merged["evidence"]), 16)

    def test_unknown_player_returns_analysis_unchanged(self) -> None:
        analysis = base_analysis(puuid="not-in-match")
        merged = merge_habit_metrics(analysis, make_match(), make_timeline([]), [])

        self.assertNotIn("gold_retention_score", merged["scores"])


if __name__ == "__main__":
    unittest.main()
