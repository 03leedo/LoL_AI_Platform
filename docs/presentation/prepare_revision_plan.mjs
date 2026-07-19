import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const slide2Targets = [
  "sh/5o7qpg3e",
  "sh/g3ex0nux",
  "sh/9cvixcze",
  "sh/gr2p8nqx",
  "sh/yd0z6103",
  "sh/wb2hwfyx",
];

const slide10Targets = [
  "sh/gvy90je9",
  "sh/94fu18jq",
  "ch/w7mp0bi9",
  "sh/rqd4vmtw",
  "sh/4fu18jqh",
  "sh/x0nuxc3y",
  "sh/m94fu18j",
  "sh/fu18jqh0",
  "sh/83itgfml",
  "sh/xobm58z2",
  "sh/qxs72x4n",
  "sh/fil0rqd4",
  "sh/4zidonyd",
  "sh/xkf6dcbu",
  "sh/xczed8v6",
  "sh/8v6psfil",
  "sh/fa9w3m94",
  "sh/qpg3ex0n",
  "sh/x4nap4r6",
  "sh/8jqh0fep",
  "sh/fyxobm58",
  "sh/xs72x4na",
];

async function main() {
  const [workspace, sourcePptx] = process.argv.slice(2);
  if (!workspace || !sourcePptx) {
    throw new Error("Usage: node prepare_revision_plan.mjs <workspace> <source.pptx>");
  }

  const inspectDir = path.join(workspace, "template-inspect");
  const presentation = await PresentationFile.importPptx(
    await FileBlob.load(sourcePptx),
  );
  const inspect = await presentation.inspect({
    kind: "slide,textbox,shape,image,table,chart",
    maxChars: 1_500_000,
  });
  await fs.writeFile(
    path.join(inspectDir, "template-inspect.ndjson"),
    inspect.ndjson || "",
    "utf8",
  );

  const outputSlides = Array.from({ length: 12 }, (_, index) => {
    const slide = index + 1;
    const ids = slide === 2 ? slide2Targets : slide === 10 ? slide10Targets : [];
    return {
      outputSlide: slide,
      sourceSlide: slide,
      narrativeRole:
        slide === 2
          ? "feature summary"
          : slide === 10
            ? "model explanation and training evidence"
            : "unchanged source slide",
      reuseMode: "duplicate-slide",
      editTargets: ids.map((shapeId) => ({
        shapeId,
        action: "rewrite",
        reason:
          slide === 2
            ? "Replace competitive claims with a neutral feature summary."
            : "Explain the per-minute win prediction model in audience-friendly language.",
      })),
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
      "Source: 12-slide LoL AI analysis platform presentation.",
      "Typography: Malgun Gothic; preserve all existing sizes, weights, and alignment.",
      "Palette: white canvas with navy text, gold eyebrow labels, and muted red/teal/blue panels.",
      "Structure: preserve every slide and edit only inherited text/chart objects on slides 2 and 10.",
      "Slide 2: replace competitor comparison with a neutral feature overview.",
      "Slide 10: keep the two-panel structure; update the data chart and simplify the model explanation.",
      "No structural placeholders were found in the edited slides.",
    ].join("\n") + "\n",
    "utf8",
  );
  await fs.writeFile(
    path.join(workspace, "deviation-log.txt"),
    [
      "Slide 2: visible copy changed; inherited geometry, colors, and typography preserved.",
      "Slide 10: visible copy and chart values/categories changed; inherited geometry and palette preserved.",
      "No new primitives, images, or slide layouts added.",
    ].join("\n") + "\n",
    "utf8",
  );
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
