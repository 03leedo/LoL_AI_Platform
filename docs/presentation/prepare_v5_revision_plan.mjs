import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const EDIT_TARGETS = {
  3: ["sh/61032lsz", "sh/w7mp0bi9"],
  4: ["sh/je9cvixc", "sh/7mp0bi9s"],
  9: [
    "sh/dg7adsji",
    "sh/onyd0z61",
    "sh/d8v6psfi",
    "sh/nuxc3ylc",
    "sh/y90je9cv",
    "sh/n29gr2p8",
    "sh/yhgn29gr",
    "sh/gn29gr2p",
    "sh/neloj2t8",
  ],
  10: [
    "sh/gvy90je9",
    "sh/94fu18jq",
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
    "sh/qd4vmtwr",
    "ch/w7mp0bi9",
  ],
  12: [
    "sh/ap4r65wj",
    "sh/za1gvy90",
    "sh/wfyxobm5",
    "sh/l0rqd4vm",
    "sh/eloj2t83",
    "sh/36hcrmhk",
    "sh/wra5gbq1",
    "sh/lc7u54zi",
    "sh/epkzupwb",
    "sh/7adsji5s",
  ],
};

async function main() {
  const [workspace, sourcePptx] = process.argv.slice(2);
  if (!workspace || !sourcePptx) {
    throw new Error(
      "Usage: node prepare_v5_revision_plan.mjs <workspace> <source.pptx>",
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
  await fs.writeFile(
    path.join(inspectDir, "template-inspect.ndjson"),
    inspect.ndjson || "",
    "utf8",
  );

  const outputSlides = Array.from({ length: 12 }, (_, index) => {
    const slide = index + 1;
    const targets = EDIT_TARGETS[slide] || [];
    return {
      outputSlide: slide,
      sourceSlide: slide,
      narrativeRole:
        slide === 3
          ? "show the data and analysis pipeline with the current metric count"
          : slide === 4
          ? "introduce the product's habit and early-lane review metrics"
          : slide === 9
            ? "show where grounded AI interpretation appears in the product"
            : slide === 10
              ? "explain per-minute win prediction training with an actual model curve"
              : slide === 12
                ? "close with product principles and the next improvement areas"
              : "preserve the existing presentation narrative",
      reuseMode: "duplicate-slide",
      editTargets: targets.map((shapeId) => ({
        shapeId,
        action:
          shapeId === "ch/w7mp0bi9" || shapeId === "sh/qd4vmtwr"
            ? "delete"
            : slide === 10
              ? "rewrite-and-reposition"
              : "rewrite",
        reason:
          slide === 3
            ? "Keep the analysis-engine metric count consistent after separating early combat from the resource comparison."
            : slide === 4
            ? "Add the implemented 10-minute same-role lane comparison to the metric overview."
            : slide === 9
              ? "Replace internal validation details with the AI report's user-facing role and usage locations."
              : slide === 10
                ? "Replace the gold comparison with a clear four-step training explanation while preserving the actual model win curve."
                : "Replace training-volume and phase counters with audience-facing product characteristics and update the model roadmap wording.",
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
      "Source: 12-slide LoL AI analysis platform presentation, v4.",
      "Audience: project reviewers who need a clear product and model explanation without ML jargon.",
      "Communication job: show how post-game data becomes measurable review signals, grounded AI feedback, and a per-minute model probability curve.",
      "Typography and palette: preserve the inherited Noto Sans KR, white, navy, gold, teal, red, and blue system.",
      "Slide 3: show 11 implemented match metrics after separating early combat impact from resource advantage.",
      "Slide 4: add the 10-minute same-role lane comparison to the metric overview.",
      "Slide 9: explain where AI interpretation is used in the product instead of focusing on sanitizer internals.",
      "Slide 10: preserve the actual model curve and use the inherited right panel for the training flow.",
      "Slide 12: replace collection/test/phase counters with product characteristics and clarify model improvement as future work.",
    ].join("\n") + "\n",
    "utf8",
  );
  await fs.writeFile(
    path.join(workspace, "deviation-log.txt"),
    [
      "Slide 4: title and bottom summary updated to include the implemented 10-minute lane comparison.",
      "Slide 3: metric count updated to 11.",
      "Slide 9: internal validation copy replaced with product usage and fallback behavior.",
      "Slide 10: gold-advantage chart and its separator deleted; inherited text slots repositioned into a four-step training explanation.",
      "Slide 12: training-volume and internal phase counters replaced with product-facing characteristics.",
      "Slides 1-2, 5-8, and 11 are preserved without edits.",
      "No new slide layouts, external assets, or parallel overlay designs are introduced.",
    ].join("\n") + "\n",
    "utf8",
  );
  await fs.writeFile(
    path.join(workspace, "source-notes.txt"),
    [
      "Per-minute model curve source: locally cached Riot match timeline KR_8304213229 served through the project's model v1 integration.",
      "The slide describes the curve as an actual stored match example and labels the model experimental.",
      "The resource comparison uses same-role GD@10, XPD@10, and CSD@10 with weights 0.45, 0.35, and 0.20.",
      "Early combat impact is separate: smoothed 10-minute kill participation plus direct same-role takedown differential.",
      "Health pressure is low-confidence evidence only and never changes either score.",
      "AI report wording reflects the implemented grounded-report flow: computed evidence remains authoritative and the rules report remains available as fallback.",
    ].join("\n") + "\n",
    "utf8",
  );
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
