import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

function setShapeText(slide, index, value) {
  const shape = slide.shapes.items[index];
  shape.text = value;
}

async function saveBlob(filePath, blob) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

async function main() {
  const [starterPptxPath, outputPath, qaDir] = process.argv.slice(2);
  if (!starterPptxPath || !outputPath || !qaDir) {
    throw new Error("Usage: node revise_slides_02_10.mjs <starter.pptx> <output.pptx> <qa-dir>");
  }

  const presentation = await PresentationFile.importPptx(
    await FileBlob.load(starterPptxPath),
  );

  const slide2 = presentation.slides.getItem(1);
  setShapeText(slide2, 0, "FEATURES");
  setShapeText(slide2, 1, "한 경기의 흐름과 반복되는 플레이를 함께 본다");
  setShapeText(slide2, 4, "경기 단위 분석");
  setShapeText(
    slide2,
    5,
    "타임라인과 주요 사건 요약\n데스 비용·리드 전환 등 플레이 지표\n미니맵 스냅샷과 킬·오브젝트 로그\n분석 근거와 신뢰도 표시",
  );
  setShapeText(slide2, 7, "누적 플레이 분석");
  setShapeText(
    slide2,
    8,
    "역할·챔피언별 경기 기록\n반복되는 사망 위치와 시간대\n대표 경기와 평소 대비 변화\n계산된 근거를 바탕으로 AI 요약",
  );

  const slide10 = presentation.slides.getItem(9);
  setShapeText(slide10, 1, "경기 흐름을 분 단위 승리 확률로 예측한다");
  setShapeText(slide10, 4, "학습 데이터 확대 과정");
  setShapeText(
    slide10,
    5,
    "현재 526경기를 사용했습니다.\n다양한 패치와 티어 데이터가 더 필요합니다.",
  );

  const chart = slide10.charts.items[0];
  const series = chart.series.getItemAt(0);
  series.values = [55, 150, 350, 526];
  series.categories = ["초기", "1차 수집", "2차 수집", "현재"];
  chart.yAxis = {
    min: 0,
    max: 600,
    majorUnit: 100,
    majorGridlines: { style: "solid", fill: "#E2E8F2", width: 1 },
    textStyle: { fill: "#5A6B7E", fontSize: 13 },
  };
  chart.dataLabels = {
    showValue: true,
    position: "outEnd",
    textStyle: { fill: "#1E2A3A", fontSize: 14 },
  };

  setShapeText(slide10, 7, "분 단위 승리 확률 예측");
  setShapeText(slide10, 8, "구분");
  setShapeText(slide10, 9, "정보 1");
  setShapeText(slide10, 10, "정보 2");
  setShapeText(slide10, 11, "상태");
  slide10.shapes.items[11].text.style = {
    fontSize: 16,
    bold: true,
    color: "#5A6B7E",
    alignment: "center",
  };
  setShapeText(slide10, 12, "입력 데이터");
  setShapeText(slide10, 13, "골드·경험치");
  setShapeText(slide10, 14, "CS·오브젝트");
  setShapeText(slide10, 15, "분 단위");
  setShapeText(slide10, 16, "예측 결과");
  setShapeText(slide10, 17, "승리 확률");
  setShapeText(slide10, 18, "변화 흐름");
  setShapeText(slide10, 19, "경기 복기");
  setShapeText(slide10, 20, "학습 현황");
  setShapeText(slide10, 21, "526경기");
  setShapeText(slide10, 22, "표본 확대");
  setShapeText(slide10, 23, "학습 필요");
  setShapeText(
    slide10,
    25,
    "각 시점까지 확인된 경기 정보만 사용합니다.\n현재는 초기 모델이며 더 많은 패치와 티어 데이터가 필요합니다.\n데이터가 쌓이면 예측 안정성과 설명력을 계속 개선할 계획입니다.",
  );

  await fs.mkdir(qaDir, { recursive: true });
  for (const slideNumber of [2, 10]) {
    const slide = presentation.slides.getItem(slideNumber - 1);
    await saveBlob(
      path.join(qaDir, `slide-${String(slideNumber).padStart(2, "0")}.png`),
      await presentation.export({ slide, format: "png", scale: 1 }),
    );
    await saveBlob(
      path.join(qaDir, `slide-${String(slideNumber).padStart(2, "0")}.layout.json`),
      await slide.export({ format: "layout" }),
    );
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
