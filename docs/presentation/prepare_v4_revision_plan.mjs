import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

async function main() {
  const [workspace, sourcePptx] = process.argv.slice(2);
  if (!workspace || !sourcePptx) {
    throw new Error(
      "Usage: node prepare_v4_revision_plan.mjs <workspace> <source.pptx>",
    );
  }

  const inspectDir = path.join(workspace, "template-inspect");
  const presentation = await PresentationFile.importPptx(
    await FileBlob.load(sourcePptx),
  );
  const inspect = await presentation.inspect({
    kind: "slide,textbox,shape,image,table,chart",
    maxChars: 1_500_000,
  });
  const ndjson = inspect.ndjson || "";
  await fs.writeFile(
    path.join(inspectDir, "template-inspect.ndjson"),
    ndjson,
    "utf8",
  );

  const targetsBySlide = new Map();
  for (const line of ndjson.split("\n")) {
    if (!line.trim()) continue;
    const item = JSON.parse(line);
    if (!item.slide || !["textbox", "chart"].includes(item.kind)) continue;
    if (!targetsBySlide.has(item.slide)) targetsBySlide.set(item.slide, []);
    targetsBySlide.get(item.slide).push({
      shapeId: item.id,
      action:
        item.id === "sh/xs72x4na"
          ? "delete"
          : item.slide === 10 && item.kind === "chart"
          ? "replace"
          : item.slide === 10
            ? "rewrite-and-reposition"
            : "rewrite",
      reason:
        item.id === "sh/xs72x4na"
          ? "Delete the inherited bulleted footer because the replacement explanation uses a non-bulleted inherited text slot."
          : item.slide === 10
          ? "Replace the training-volume explanation with an actual per-minute estimated win-probability example and improve typography."
          : "Apply the requested larger Noto Sans KR typography while preserving the inherited layout.",
    });
  }

  const outputSlides = Array.from({ length: 12 }, (_, index) => {
    const slide = index + 1;
    const editTargets = targetsBySlide.get(slide) || [];
    if (slide === 10) {
      editTargets.push({
        action: "add",
        newPrimitiveAllowed: true,
        zone: { left: 696, top: 249, width: 499, height: 315 },
        mustNotOverlapInherited: true,
        reason:
          "Use the cleared inherited right-panel content zone for an editable gold-advantage line chart requested by the user.",
      });
    }
    return {
      outputSlide: slide,
      sourceSlide: slide,
      narrativeRole:
        slide === 10
          ? "show how per-minute estimated win probability reveals turning points"
          : "preserve the existing presentation narrative with improved legibility",
      reuseMode: "duplicate-slide",
      editTargets,
    };
  });

  await fs.writeFile(
    path.join(workspace, "template-frame-map.json"),
    `${JSON.stringify({ outputSlides, omittedSourceSlides: [] }, null, 2)}\n`,
    "utf8",
  );
  await fs.writeFile(
    path.join(workspace, "template-audit.txt"),
    [
      "Source: 12-slide LoL AI analysis platform presentation, v3.",
      "Audience: project reviewers who need to understand the product and its analysis flow quickly.",
      "Communication job: show that the product turns match data into an understandable post-game review, including a transparent per-minute estimated win-probability curve.",
      "Typography: replace Malgun Gothic with Noto Sans KR and enlarge small text while preserving hierarchy.",
      "Palette and structure: preserve the inherited white, navy, gold, teal, red, and blue visual system and all 12 slide layouts.",
      "Slide 10: reuse the inherited two-panel layout; show the trained model's per-minute win prediction on the left and the same match's observed gold advantage on the right.",
      "No new slides or parallel overlay layouts are introduced.",
    ].join("\n") + "\n",
    "utf8",
  );
  await fs.writeFile(
    path.join(workspace, "deviation-log.txt"),
    [
      "Slides 1-12: font family changed to Noto Sans KR and smaller text enlarged at the user's request.",
      "Slide 10: inherited bar chart changed to the trained model's line chart using an actual stored match timeline.",
      "Slide 10: inherited right-panel table labels were cleared and its bounded content zone now contains an editable gold-advantage line chart.",
      "Slide 10: training-volume claims removed because they do not help the audience understand the feature.",
      "No new primitives, images, or slide layouts added.",
    ].join("\n") + "\n",
    "utf8",
  );
  await fs.writeFile(
    path.join(workspace, "source-notes.txt"),
    [
      "Per-minute curves source: locally cached Riot match timeline KR_8304213229, retrieved from the project's own backend API after model-serving integration.",
      "The public-facing slide omits the match ID and describes it as an actual stored match example.",
      "Win curve source: model v1, dataset v2, explicitly labeled experimental because the latest adoption verdict remains keep_heuristic by Brier score.",
      "Advantage curve source: observed blue-minus-red gold difference from the same minute frames; it is not a model probability.",
    ].join("\n") + "\n",
    "utf8",
  );
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
