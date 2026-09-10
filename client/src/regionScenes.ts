import type { BodyRegionId } from "./bodyRegions";

export type RegionScene = {
  region: BodyRegionId | "default";
  image: string;
  titleEn: string;
  titleHi: string;
};

/** Hero art for interview scenes — always the full-body figure.
 *  Brain / heart live only in the bottom dock cards, not as competing heroes.
 */
export const REGION_SCENES: Record<BodyRegionId | "default", RegionScene> = {
  default: {
    region: "default",
    image: "/bodyimages/firstpage.png",
    titleEn: "Diagnose and monitor your symptoms",
    titleHi: "लक्षण पहचानें और बताएँ",
  },
  head: {
    region: "head",
    image: "/bodyimages/firstpage.png",
    titleEn: "Head & nervous system",
    titleHi: "सिर और तंत्रिका तंत्र",
  },
  neck: {
    region: "neck",
    image: "/bodyimages/firstpage.png",
    titleEn: "Neck & throat",
    titleHi: "गर्दन और गला",
  },
  chest: {
    region: "chest",
    image: "/bodyimages/firstpage.png",
    titleEn: "Chest & heart",
    titleHi: "छाती और हृदय",
  },
  abdomen: {
    region: "abdomen",
    image: "/bodyimages/firstpage.png",
    titleEn: "Abdomen",
    titleHi: "पेट",
  },
  pelvis: {
    region: "pelvis",
    image: "/bodyimages/firstpage.png",
    titleEn: "Pelvis & lower back",
    titleHi: "कमर",
  },
  left_arm: {
    region: "left_arm",
    image: "/bodyimages/firstpage.png",
    titleEn: "Left arm",
    titleHi: "बायाँ हाथ",
  },
  right_arm: {
    region: "right_arm",
    image: "/bodyimages/firstpage.png",
    titleEn: "Right arm",
    titleHi: "दायाँ हाथ",
  },
  left_leg: {
    region: "left_leg",
    image: "/bodyimages/firstpage.png",
    titleEn: "Left leg",
    titleHi: "बायाँ पैर",
  },
  right_leg: {
    region: "right_leg",
    image: "/bodyimages/firstpage.png",
    titleEn: "Right leg",
    titleHi: "दायाँ पैर",
  },
  back: {
    region: "back",
    image: "/bodyimages/firstpage.png",
    titleEn: "Back",
    titleHi: "पीठ",
  },
};

export function sceneForRegions(regions: BodyRegionId[]): RegionScene {
  const primary = regions[0];
  if (primary && REGION_SCENES[primary]) return REGION_SCENES[primary];
  return REGION_SCENES.default;
}
