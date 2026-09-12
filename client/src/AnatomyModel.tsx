import { Suspense, memo, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { Bounds, OrbitControls, useBounds, useGLTF } from "@react-three/drei";
import * as THREE from "three";
import type { BodyRegionId } from "./bodyRegions";
import "./AnatomyModel.css";

/**
 * Free/open anatomy asset: Z-Anatomy dataset (CC BY-SA 4.0), re-exported as a
 * browser-ready Draco-compressed GLB by github.com/hpfrei/body-anatomy-3d-viewer.
 * Attribution is rendered on-screen (required by the license) — see the
 * `.anat-credit` element below. Do not remove that credit line.
 */
const MODEL_URL = "/models/body.glb";

useGLTF.preload(MODEL_URL, true);

const REGION_KEYWORDS: Record<BodyRegionId, string[]> = {
  head: [
    "skull",
    "cranial",
    "parietal",
    "occipital",
    "frontal bone",
    "temporal bone",
    "sphenoid",
    "ethmoid",
    "maxilla",
    "mandible",
    "nasal bone",
    "zygomatic",
    "lacrimal",
    "palatine bone",
    "hyoid",
    "masseter",
    "temporalis muscle",
    "frontalis",
    "orbicularis oculi",
    "buccinator",
  ],
  neck: [
    "cervical vertebra",
    "larynx",
    "thyroid cartilage",
    "sternocleidomastoid",
    "platysma",
    "scalene",
    "longus colli",
  ],
  chest: [
    "rib",
    "sternum",
    "thorac",
    "pector",
    "intercostal",
    "costal cartilage",
    "serratus anterior",
    "xiphoid",
  ],
  abdomen: [
    "lumbar vertebra",
    "rectus abdominis",
    "oblique",
    "transversus abdominis",
    "abdominal",
    "linea alba",
  ],
  pelvis: [
    "pelvis",
    "ilium",
    "ischium",
    "pubis",
    "sacrum",
    "coccyx",
    "iliopsoas",
    "piriformis",
    "obturator",
  ],
  back: [
    "thoracic vertebra",
    "spinous process",
    "erector spinae",
    "latissimus dorsi",
    "trapezius",
    "rhomboid",
    "scapula",
    "teres major",
    "teres minor",
    "infraspinatus",
    "supraspinatus",
  ],
  left_arm: [
    "humerus",
    "radius",
    "ulna",
    "carpal",
    "metacarpal",
    "phalanx of hand",
    "deltoid",
    "biceps brachii",
    "triceps brachii",
    "brachialis",
    "brachioradialis",
    "pronator",
    "supinator",
    "flexor carpi",
    "extensor carpi",
    "flexor digitorum",
    "extensor digitorum",
    "palmaris longus",
    "anconeus",
    "clavicle",
  ],
  right_arm: [
    "humerus",
    "radius",
    "ulna",
    "carpal",
    "metacarpal",
    "phalanx of hand",
    "deltoid",
    "biceps brachii",
    "triceps brachii",
    "brachialis",
    "brachioradialis",
    "pronator",
    "supinator",
    "flexor carpi",
    "extensor carpi",
    "flexor digitorum",
    "extensor digitorum",
    "palmaris longus",
    "anconeus",
    "clavicle",
  ],
  left_leg: [
    "femur",
    "tibia",
    "fibula",
    "patella",
    "tarsal",
    "metatarsal",
    "phalanx of foot",
    "quadriceps",
    "vastus",
    "rectus femoris",
    "hamstring",
    "biceps femoris",
    "semitendinosus",
    "semimembranosus",
    "adductor",
    "tensor fasciae latae",
    "gastrocnemius",
    "soleus",
    "tibialis anterior",
    "peroneus",
    "fibularis",
    "sartorius",
    "gluteus",
  ],
  right_leg: [
    "femur",
    "tibia",
    "fibula",
    "patella",
    "tarsal",
    "metatarsal",
    "phalanx of foot",
    "quadriceps",
    "vastus",
    "rectus femoris",
    "hamstring",
    "biceps femoris",
    "semitendinosus",
    "semimembranosus",
    "adductor",
    "tensor fasciae latae",
    "gastrocnemius",
    "soleus",
    "tibialis anterior",
    "peroneus",
    "fibularis",
    "sartorius",
    "gluteus",
  ],
};

const LATERAL_REGIONS: Partial<Record<BodyRegionId, "l" | "r">> = {
  left_arm: "l",
  right_arm: "r",
  left_leg: "l",
  right_leg: "r",
};

function sideOf(nameLower: string): "l" | "r" | null {
  if (/\bleft\b/.test(nameLower)) return "l";
  if (/\bright\b/.test(nameLower)) return "r";
  const m = nameLower.match(/\.(l|r)(\.\d+)?$/);
  return m ? (m[1] as "l" | "r") : null;
}

type RegionGroups = Partial<Record<BodyRegionId, THREE.Mesh[]>>;

function buildRegionGroups(root: THREE.Object3D): RegionGroups {
  const groups: RegionGroups = {};

  root.traverse((child) => {
    const mesh = child as THREE.Mesh;
    if (!mesh.isMesh) return;
    if (!mesh.userData.__origMaterial) mesh.userData.__origMaterial = mesh.material;

    const nameLower = mesh.name.toLowerCase();
    const side = sideOf(nameLower);

    (Object.keys(REGION_KEYWORDS) as BodyRegionId[]).forEach((region) => {
      const hit = REGION_KEYWORDS[region].some((kw) => nameLower.includes(kw));
      if (!hit) return;
      const wantSide = LATERAL_REGIONS[region];
      // Many muscle meshes in this dataset aren't tagged with an explicit
      // .l/.r suffix (only bones consistently are), so a mesh with no
      // detectable side is treated as ambiguous and included on both sides
      // rather than dropped — otherwise visible surface muscles never light
      // up and only hidden internal bones would match.
      if (!wantSide || side === null || side === wantSide) {
        (groups[region] ??= []).push(mesh);
      }
    });
  });

  return groups;
}

const HIGHLIGHT_COLOR = new THREE.Color("#d99a52");

function Model({
  activeRegions,
  onReady,
}: {
  activeRegions: BodyRegionId[];
  onReady: () => void;
}) {
  const { scene } = useGLTF(MODEL_URL, true);
  const cloned = useMemo(() => scene.clone(true), [scene]);
  const groupsRef = useRef<RegionGroups>({});
  const { invalidate } = useThree();

  useEffect(() => {
    groupsRef.current = buildRegionGroups(cloned);
    // Subtle default material tint so the figure reads on the stage.
    cloned.traverse((child) => {
      const mesh = child as THREE.Mesh;
      if (!mesh.isMesh) return;
      const mat = mesh.userData.__origMaterial as THREE.Material | THREE.Material[];
      const apply = (m: THREE.Material) => {
        if (m instanceof THREE.MeshStandardMaterial) {
          m.color = new THREE.Color("#c7d4e0");
          m.roughness = 0.55;
          m.metalness = 0.05;
        }
      };
      if (Array.isArray(mat)) mat.forEach(apply);
      else if (mat) apply(mat);
    });
    onReady();
    invalidate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cloned]);

  const regionKey = activeRegions.join(",");

  useEffect(() => {
    const groups = groupsRef.current;
    const active = new Set(activeRegions);
    (Object.keys(groups) as BodyRegionId[]).forEach((region) => {
      const meshes = groups[region];
      if (!meshes) return;
      const isActive = active.has(region);
      meshes.forEach((mesh) => {
        if (isActive) {
          if (!mesh.userData.__highlightMaterial) {
            const base = mesh.userData.__origMaterial as THREE.Material;
            const src = Array.isArray(base) ? base[0] : base;
            const clone = (src as THREE.MeshStandardMaterial).clone();
            clone.color = HIGHLIGHT_COLOR.clone();
            clone.emissive = HIGHLIGHT_COLOR;
            clone.emissiveIntensity = 0.85;
            mesh.userData.__highlightMaterial = clone;
          }
          mesh.material = mesh.userData.__highlightMaterial as THREE.Material;
        } else {
          mesh.material = mesh.userData.__origMaterial as THREE.Material;
        }
      });
    });
    invalidate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [regionKey, invalidate]);

  return <primitive object={cloned} />;
}

/** Fit the camera once after the model is ready — never again on speak/reflow. */
function FitOnce({ ready }: { ready: boolean }) {
  const api = useBounds();
  const fitted = useRef(false);
  const { invalidate } = useThree();

  useLayoutEffect(() => {
    if (!ready || fitted.current) return;
    fitted.current = true;
    // Wait two frames so Canvas has its final pixel size before measuring.
    let raf2 = 0;
    const raf1 = requestAnimationFrame(() => {
      raf2 = requestAnimationFrame(() => {
        api.refresh().fit();
        invalidate();
      });
    });
    return () => {
      cancelAnimationFrame(raf1);
      cancelAnimationFrame(raf2);
    };
  }, [ready, api, invalidate]);

  return null;
}

type Props = {
  activeRegions: BodyRegionId[];
  theme?: "dark" | "light";
  className?: string;
};

function AnatomyModel({
  activeRegions,
  theme = "dark",
  className,
}: Props) {
  const [modelReady, setModelReady] = useState(false);

  return (
    <div className={`anat-viewport anat-viewport--${theme} ${className ?? ""}`}>
      <Canvas
        dpr={[1, 1.25]}
        frameloop="demand"
        gl={{
          antialias: true,
          alpha: true,
          powerPreference: "high-performance",
        }}
        camera={{ fov: 38, near: 0.1, far: 80, position: [0, 1.0, 3.4] }}
        resize={{ debounce: 250 }}
      >
        <ambientLight intensity={theme === "light" ? 0.95 : 0.75} />
        <directionalLight
          position={[3, 5, 4]}
          intensity={theme === "light" ? 0.9 : 1.0}
        />
        <directionalLight
          position={[-4, -2, -3]}
          intensity={theme === "light" ? 0.4 : 0.3}
        />
        <Suspense fallback={null}>
          {/* fit={false} + observe={false}: camera only moves via FitOnce */}
          <Bounds fit={false} clip={false} observe={false} margin={1.45}>
            <Model
              activeRegions={activeRegions}
              onReady={() => setModelReady(true)}
            />
            <FitOnce ready={modelReady} />
          </Bounds>
        </Suspense>
        <OrbitControls
          makeDefault
          enablePan={false}
          enableZoom={false}
          autoRotate={false}
          minPolarAngle={Math.PI * 0.4}
          maxPolarAngle={Math.PI * 0.6}
        />
      </Canvas>
      <p className="anat-credit">
        3D anatomy:{" "}
        <a href="https://www.z-anatomy.com/" target="_blank" rel="noreferrer">
          Z-Anatomy
        </a>{" "}
        · CC BY-SA 4.0
      </p>
    </div>
  );
}

export default memo(AnatomyModel, (prev, next) => {
  return (
    prev.theme === next.theme &&
    prev.className === next.className &&
    prev.activeRegions.join(",") === next.activeRegions.join(",")
  );
});
