import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const FONT = "Noto Sans KR";
const MODEL_WIN_PROBABILITY = [
  52.7, 52.5, 47, 46.6, 51.2, 54, 44.7, 41.9, 38.3, 39.7,
  60.8, 63.3, 60.5, 71.6, 73.5, 54.8, 51.7, 61.1, 65.2, 63,
  73.8, 72.1, 52.7, 40.4, 43.8, 45.5, 56.9, 77.7, 73.3, 61.8,
  62.3, 68.5, 71.2, 78, 75, 74.1, 64.6,
];
const GOLD_ADVANTAGE = [
  0, -5, -119, -261, 421, 750, 570, 222, -219, -109,
  1722, 2117, 2061, 2794, 3301, 465, 283, 826, 1539, 1024,
  1963, 1636, -574, -1609, -891, -792, 193, 2179, 2280, 846,
  -197, 773, 2121, 3175, 3178, 2764, 1971,
];

function scaledFontSize(size) {
  if (!Number.isFinite(size)) return size;
  if (size <= 12) return 16;
  if (size <= 15.5) return 18;
  if (size <= 17.5) return 19;
  if (size <= 20.5) return 22;
  if (size <= 22.5) return 24;
  if (size <= 24.5) return 26;
  if (size <= 27.5) return 30;
  if (size <= 41) return 44;
  if (size <= 47) return 48;
  return size;
}

function styleText(shape, { fontSize, bold, color, alignment } = {}) {
  if (!shape?.text) return;
  const previousSize = shape.text.fontSize;
  shape.text.style = {
    typeface: FONT,
    ...(fontSize ? { fontSize } : {}),
    ...(bold === undefined ? {} : { bold }),
    ...(color ? { color } : {}),
    ...(alignment ? { alignment } : {}),
  };
  if (!fontSize && Number.isFinite(previousSize)) {
    shape.text.fontSize = scaledFontSize(previousSize);
  }
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

async function main() {
  const [starterPptxPath, outputPath, qaDir] = process.argv.slice(2);
  if (!starterPptxPath || !outputPath || !qaDir) {
    throw new Error(
      "Usage: node revise_deck_v4.mjs <starter.pptx> <output.pptx> <qa-dir>",
    );
  }

  const presentation = await PresentationFile.importPptx(
    await FileBlob.load(starterPptxPath),
  );

  for (const slide of presentation.slides.items) {
    for (const shape of slide.shapes.items) styleText(shape);
    for (const chart of slide.charts.items) {
      chart.xAxis = {
        ...(chart.xAxis || {}),
        textStyle: { fill: "#5A6B7E", fontSize: 16, typeface: FONT },
      };
      chart.yAxis = {
        ...(chart.yAxis || {}),
        textStyle: { fill: "#5A6B7E", fontSize: 16, typeface: FONT },
      };
      chart.legend = {
        ...(chart.legend || {}),
        textStyle: { fill: "#5A6B7E", fontSize: 16, typeface: FONT },
      };
    }
  }

  for (let slideIndex = 1; slideIndex < presentation.slides.items.length; slideIndex += 1) {
    const eyebrow = presentation.slides.getItem(slideIndex).shapes.items[0];
    if (!eyebrow?.text) continue;
    styleText(eyebrow, { fontSize: 18 });
    position(
      eyebrow,
      eyebrow.position.left,
      eyebrow.position.top,
      Math.max(360, eyebrow.position.width),
      eyebrow.position.height,
    );
  }

  const slide10 = presentation.slides.getItem(9);
  setText(
    slide10,
    1,
    "각 분의 모델 승률과 실제 우세도를 함께 본다",
    { fontSize: 44, bold: true, color: "#1E2A3A" },
  );
  setText(slide10, 4, "모델 예상 승률", {
    fontSize: 22,
    bold: true,
    color: "#1E2A3A",
  });
  setText(
    slide10,
    5,
    "모델 v1 · 데이터셋 v2 · 실제 저장 경기 예시",
    { fontSize: 18, color: "#5A6B7E" },
  );

  const inheritedChart = slide10.charts.items[0];
  slide10.charts.deleteById(inheritedChart.id);
  slide10.charts.add("line", {
    position: { left: 78, top: 245, width: 530, height: 326 },
    categories: MODEL_WIN_PROBABILITY.map((_, minute) => `${minute}분`),
    series: [
      {
        name: "블루팀 모델 예상 승률",
        values: MODEL_WIN_PROBABILITY,
        fill: "#0B7A70",
      },
    ],
    hasLegend: false,
    dataLabels: { showValue: false },
    xAxis: {
      textStyle: { fill: "#5A6B7E", fontSize: 14, typeface: FONT },
      majorGridlines: { style: "solid", fill: "#EEF2F7", width: 1 },
    },
    yAxis: {
      min: 0,
      max: 100,
      majorUnit: 25,
      textStyle: { fill: "#5A6B7E", fontSize: 14, typeface: FONT },
      majorGridlines: { style: "solid", fill: "#D8E0EA", width: 1 },
    },
  });

  setText(slide10, 7, "골드 우세도", {
    fontSize: 22,
    bold: true,
    color: "#1E2A3A",
  });
  for (const index of [8, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]) {
    setText(slide10, index, "", { fontSize: 16 });
  }
  const inheritedBulletedFooter = slide10.shapes.items[25];
  slide10.shapes.deleteById(inheritedBulletedFooter.id);

  slide10.charts.add("line", {
    position: { left: 683, top: 245, width: 526, height: 305 },
    categories: GOLD_ADVANTAGE.map((_, minute) => `${minute}분`),
    series: [
      {
        name: "블루팀 골드 우세도",
        values: GOLD_ADVANTAGE,
        fill: "#C89B3C",
      },
    ],
    hasLegend: false,
    dataLabels: { showValue: false },
    xAxis: {
      textStyle: { fill: "#5A6B7E", fontSize: 14, typeface: FONT },
      majorGridlines: { style: "solid", fill: "#EEF2F7", width: 1 },
    },
    yAxis: {
      min: -4000,
      max: 4000,
      majorUnit: 2000,
      textStyle: { fill: "#5A6B7E", fontSize: 14, typeface: FONT },
      majorGridlines: { style: "solid", fill: "#D8E0EA", width: 1 },
    },
  });

  setText(
    slide10,
    12,
    "승률은 매 분의 상황을 입력한 학습 모델 결과이며 아직 실험 단계입니다.\n우세도는 같은 시점의 실제 블루팀−레드팀 골드 차이입니다.",
    { fontSize: 16, color: "#5A6B7E" },
  );
  position(slide10.shapes.items[12], 696, 570, 499, 72);

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
