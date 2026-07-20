import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const FONT = "Noto Sans KR";

function styleText(shape, { fontSize, bold, color, alignment } = {}) {
  if (!shape?.text) return;
  shape.text.style = {
    typeface: FONT,
    ...(fontSize ? { fontSize } : {}),
    ...(bold === undefined ? {} : { bold }),
    ...(color ? { color } : {}),
    ...(alignment ? { alignment } : {}),
  };
}

function setText(slide, index, value, style = {}) {
  const shape = slide.shapes.items[index];
  shape.text = value;
  styleText(shape, style);
  return shape;
}

function position(shape, left, top, width, height) {
  shape.position = { left, top, width, height };
}

async function saveBlob(filePath, blob) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

function updateArchitecture(presentation) {
  const slide = presentation.slides.getItem(2);
  setText(slide, 13, "지표 11종·에피소드\n프로필·패턴 (규칙 계산)", {
    fontSize: 18,
    color: "#FFFFFF",
    alignment: "center",
  });
  setText(
    slide,
    24,
    "모든 수치·패턴은 규칙 코드가 계산 — LLM은 새 숫자를 만들 수 없음 (환각 통제 + 비용 절감)\n원본 JSONB 보존 + 지표 버전 관리 — 공식이 바뀌면 재수집 없이 전체 재계산\nDocker Compose 로컬 스택 (FastAPI · Next.js · PostgreSQL 16) — 자동 회귀 테스트 통과 유지",
    { fontSize: 18, color: "#334155" },
  );
}

function updateMetricOverview(presentation) {
  const slide = presentation.slides.getItem(3);
  setText(slide, 1, "경기 복기 — 습관과 초반 흐름을 수치화", {
    fontSize: 44,
    bold: true,
    color: "#1E2A3A",
  });
  setText(
    slide,
    28,
    "+ 10분 자원 우세도 · 초반 교전 영향력 · 체력 압박 참고 신호\n오브젝트 준비 · 리드 전환 · 변곡점 · 킬/데스 히트맵",
    { fontSize: 18, bold: true, color: "#0B7A70" },
  );
}

function updateAiReport(presentation) {
  const slide = presentation.slides.getItem(8);
  setText(slide, 1, "AI는 계산된 근거를 복기할 문장으로 바꾼다", {
    fontSize: 44,
    bold: true,
    color: "#1E2A3A",
  });

  setText(slide, 4, "계산된 근거", {
    fontSize: 22,
    bold: true,
    color: "#FFFFFF",
    alignment: "center",
  });
  setText(slide, 5, "지표 · 이벤트 · 미니맵\n신뢰도와 한계", {
    fontSize: 18,
    color: "#FFFFFF",
    alignment: "center",
  });
  setText(slide, 8, "AI 해석", {
    fontSize: 22,
    bold: true,
    color: "#FFFFFF",
    alignment: "center",
  });
  setText(slide, 9, "반복 패턴을 요약하고\n근거가 있는 피드백을 작성", {
    fontSize: 18,
    color: "#FFFFFF",
    alignment: "center",
  });
  setText(slide, 12, "복기 화면", {
    fontSize: 22,
    bold: true,
    color: "#FFFFFF",
    alignment: "center",
  });
  setText(slide, 13, "관찰 · 개선 제안\n다음 리플레이 질문", {
    fontSize: 18,
    color: "#FFFFFF",
    alignment: "center",
  });

  setText(slide, 15, "AI 리포트가 쓰이는 곳", {
    fontSize: 24,
    bold: true,
    color: "#1E2A3A",
  });
  setText(
    slide,
    16,
    "경기 상세 — 주요 사건마다 상황과 손해 가능성을 설명\n누적 리포트 — 최근 경기에서 반복되는 강점과 약점을 요약\n복기 질문 — 리플레이에서 다시 확인할 장면을 제안\nAI 응답이 없어도 같은 지표와 규칙 리포트를 그대로 제공",
    { fontSize: 21, color: "#334155" },
  );
}

function updateModelSlide(presentation) {
  const slide = presentation.slides.getItem(9);
  setText(slide, 1, "매 분의 경기 상태로 그 시점의 승리 가능성을 학습한다", {
    fontSize: 42,
    bold: true,
    color: "#1E2A3A",
  });
  setText(slide, 4, "실제 경기의 모델 예상 승률", {
    fontSize: 22,
    bold: true,
    color: "#1E2A3A",
  });
  setText(slide, 5, "실제 저장 경기 예시 · 0분부터 경기 종료까지", {
    fontSize: 18,
    color: "#5A6B7E",
  });
  setText(slide, 7, "모델은 이렇게 학습한다", {
    fontSize: 22,
    bold: true,
    color: "#1E2A3A",
  });

  const rows = [
    {
      headerIndex: 8,
      bodyIndex: 9,
      title: "01  매 분 스냅샷",
      body: "골드 · XP · CS · 타워 · 오브젝트",
    },
    {
      headerIndex: 10,
      bodyIndex: 11,
      title: "02  최종 승패 연결",
      body: "각 시점에 그 경기의 최종 결과를 라벨로 부여",
    },
    {
      headerIndex: 13,
      bodyIndex: 14,
      title: "03  경기 단위 검증",
      body: "같은 경기의 분 데이터가 학습과 테스트에 섞이지 않게 분리",
    },
    {
      headerIndex: 15,
      bodyIndex: 16,
      title: "04  분당 승률 출력",
      body: "미래 프레임 없이 해당 분까지의 정보로 예측",
    },
  ];

  rows.forEach((row, index) => {
    const top = 258 + index * 70;
    const header = setText(slide, row.headerIndex, row.title, {
      fontSize: 18,
      bold: true,
      color: "#B7791F",
    });
    position(header, 696, top, 188, 52);
    const body = setText(slide, row.bodyIndex, row.body, {
      fontSize: 17,
      color: "#334155",
    });
    position(body, 884, top, 311, 52);
  });

  for (const index of [17, 18, 19, 20, 21, 22, 23]) {
    setText(slide, index, "", { fontSize: 16 });
  }

  setText(
    slide,
    12,
    "현재 모델은 실험 단계이며 성능 게이트를 아직 통과하지 못했습니다.\n그래프는 기능 검증용 실제 저장 경기 예시입니다.",
    { fontSize: 17, color: "#5A6B7E" },
  );
  position(slide.shapes.items[12], 696, 548, 499, 92);

  const separator = slide.shapes.items[24];
  slide.shapes.deleteById(separator.id);
  const rightChart = slide.charts.items[1];
  slide.charts.deleteById(rightChart.id);
}

function updateLocalCollector(presentation) {
  const slide = presentation.slides.getItem(10);
  setText(slide, 0, "확장 기능", {
    fontSize: 18,
    bold: true,
    color: "#D29B2E",
  });
  setText(slide, 1, "선택형 로컬 수집 — 경기 후 분석을 더 세밀하게", {
    fontSize: 42,
    bold: true,
    color: "#1E2A3A",
  });
  setText(slide, 5, "게임 시작을 감지하고\n1초마다 상태를 확인", {
    fontSize: 17,
    color: "#E8EEF6",
    alignment: "center",
  });
  setText(slide, 9, "체력·골드·이벤트를\n내 PC에 임시 저장", {
    fontSize: 17,
    color: "#E8EEF6",
    alignment: "center",
  });
  setText(
    slide,
    13,
    "전송이 끊겨도 이어서 업로드\n같은 경기는 중복 저장하지 않음",
    { fontSize: 17, color: "#E8EEF6", alignment: "center" },
  );
  setText(slide, 17, "Riot ID와 시작 시각으로\n내 전적에 자동 연결", {
    fontSize: 17,
    color: "#FFFFFF",
    alignment: "center",
  });
  setText(slide, 19, "사용자가 직접 켜는 선택 수집", {
    fontSize: 19,
    bold: true,
    color: "#0B7A70",
  });
  setText(slide, 20, "경기 중에는 분석·조언을 표시하지 않고, 본인 게임만 수집", {
    fontSize: 17,
    color: "#334155",
  });
  setText(slide, 22, "분석 근거 보강", {
    fontSize: 19,
    bold: true,
    color: "#0B7A70",
  });
  setText(slide, 23, "초 단위 체력·골드 변화로 위험 구간과 사망 전후 흐름을 더 세밀하게 복기", {
    fontSize: 17,
    color: "#334155",
  });
  setText(slide, 25, "가볍게 실행", {
    fontSize: 19,
    bold: true,
    color: "#0B7A70",
  });
  setText(slide, 26, "게임 PC에서 실행하는 가벼운 단일 프로그램", {
    fontSize: 17,
    color: "#334155",
  });
}

function updateRoadmap(presentation) {
  const slide = presentation.slides.getItem(11);
  const roadmap = [
    {
      titleIndex: 6,
      bodyIndex: 7,
      title: "역할별 플레이 분석 확장",
      body: "탑·정글·미드·원딜·서포터마다 다른 역할과 판단 기준으로 지표를 분리",
    },
    {
      titleIndex: 10,
      bodyIndex: 11,
      title: "지표 신뢰도 높이기",
      body: "패치·티어·챔피언 상성별 기준값을 쌓고, 리플레이 검증으로 점수와 신뢰도를 보정",
    },
    {
      titleIndex: 14,
      bodyIndex: 15,
      title: "분당 승률 모델 개선",
      body: "더 다양한 경기로 학습하고, 검증 기준을 통과한 모델만 서비스에 반영",
    },
    {
      titleIndex: 18,
      bodyIndex: 19,
      title: "리플레이 분석 확장",
      body: "미니맵에서 10인 위치와 시야를 추출해 주요 장면의 판단 근거를 보강",
    },
  ];
  for (const item of roadmap) {
    setText(slide, item.titleIndex, item.title, {
      fontSize: 24,
      bold: true,
      color: "#FFFFFF",
    });
    setText(slide, item.bodyIndex, item.body, {
      fontSize: 18,
      color: "#B8C4D1",
    });
  }

  const summary = [
    [20, "1분", 44],
    [21, "승률 예측 단위", 18],
    [22, "11종", 44],
    [23, "경기 지표", 18],
    [24, "근거", 40],
    [25, "AI 입력 원칙", 18],
    [26, "경기 후", 34],
    [27, "분석 범위", 18],
  ];
  for (const [index, value, fontSize] of summary) {
    setText(slide, index, value, {
      fontSize,
      bold: index % 2 === 0,
      color: index % 2 === 0 ? "#0B7A70" : "#5A6B7E",
      alignment: "center",
    });
  }
}

async function main() {
  const [starterPptxPath, outputPath, qaDir] = process.argv.slice(2);
  if (!starterPptxPath || !outputPath || !qaDir) {
    throw new Error(
      "Usage: node revise_deck_v5.mjs <starter.pptx> <output.pptx> <qa-dir>",
    );
  }

  const presentation = await PresentationFile.importPptx(
    await FileBlob.load(starterPptxPath),
  );

  updateArchitecture(presentation);
  updateMetricOverview(presentation);
  updateAiReport(presentation);
  updateModelSlide(presentation);
  updateLocalCollector(presentation);
  updateRoadmap(presentation);

  await fs.mkdir(qaDir, { recursive: true });
  for (const [index, slide] of presentation.slides.items.entries()) {
    const stem = `slide-${String(index + 1).padStart(2, "0")}`;
    await saveBlob(
      path.join(qaDir, `${stem}.png`),
      await presentation.export({ slide, format: "png", scale: 1 }),
    );
    const layout = await slide.export({ format: "layout" });
    await fs.writeFile(path.join(qaDir, `${stem}.layout.json`), await layout.text());
  }
  await saveBlob(
    path.join(qaDir, "montage.webp"),
    await presentation.export({ format: "webp", montage: true, scale: 1 }),
  );

  const pptx = await PresentationFile.exportPptx(presentation);
  await pptx.save(outputPath);
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
