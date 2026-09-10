import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { Bounds, Html, OrbitControls, useGLTF } from "@react-three/drei";
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

function worldCenter(meshes: THREE.Mesh[]): [number, number, number] | null {
  const box = new THREE.Box3();
  let any = false;
  meshes.forEach((mesh) => {
    mesh.updateWorldMatrix(true, false);
    box.expandByObject(mesh);
    any = true;
  });
  if (!any || box.isEmpty()) return null;
  const c = box.getCenter(new THREE.Vector3());
  return [c.x, c.y, c.z];
}

const HIGHLIGHT_COLOR = new THREE.Color("#4f8bff");

function Model({
  activeRegions,
  onGroupsReady,
}: {
  activeRegions: BodyRegionId[];
  onGroupsReady: (groups: RegionGroups) => void;
}) {
  const { scene } = useGLTF(MODEL_URL, true);
  const cloned = useMemo(() => scene.clone(true), [scene]);
  const groupsRef = useRef<RegionGroups>({});

  useEffect(() => {
    groupsRef.current = buildRegionGroups(cloned);
    onGroupsReady(groupsRef.current);
    // Subtle default material tint so the figure reads on a dark stage.
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cloned]);

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
            clone.emissiveIntensity = 1.1;
            mesh.userData.__highlightMaterial = clone;
          }
          mesh.material = mesh.userData.__highlightMaterial as THREE.Material;
        } else {
          mesh.material = mesh.userData.__origMaterial as THREE.Material;
        }
      });
    });
  }, [activeRegions]);

  return <primitive object={cloned} />;
}

type Hotspot = { region: BodyRegionId; position: [number, number, number] };

function Loader() {
  return (
    <Html center>
      <div className="anat-loading">Loading 3D anatomy…</div>
    </Html>
  );
}

type Props = {
  activeRegions: BodyRegionId[];
  theme?: "dark" | "light";
  className?: string;
};

export default function AnatomyModel({
  activeRegions,
  theme = "dark",
  className,
}: Props) {
  const [groups, setGroups] = useState<RegionGroups>({});
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const regionKey = activeRegions.join(",");
  const canvasBg = theme === "light" ? "#f3ebe3" : "#0a0f1c";

  useEffect(() => {
    const id = window.setTimeout(() => {
      const next: Hotspot[] = [];
      activeRegions.forEach((region) => {
        const meshes = groups[region];
        if (!meshes?.length) return;
        const center = worldCenter(meshes);
        if (center) next.push({ region, position: center });
      });
      setHotspots(next);
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, 220);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [groups, regionKey]);

  return (
    <div className={`anat-viewport anat-viewport--${theme} ${className ?? ""}`}>
      <Canvas
        dpr={[1, 1.8]}
        gl={{ antialias: true, alpha: true }}
        camera={{ fov: 42, near: 0.05, far: 50 }}
      >
        <color attach="background" args={[canvasBg]} />
        <ambientLight intensity={theme === "light" ? 0.95 : 0.75} />
        <directionalLight
          position={[3, 5, 4]}
          intensity={theme === "light" ? 0.95 : 1.1}
        />
        <directionalLight
          position={[-4, -2, -3]}
          intensity={theme === "light" ? 0.45 : 0.35}
        />
        <Suspense fallback={<Loader />}>
          <Bounds fit clip observe margin={1.25}>
            <Model activeRegions={activeRegions} onGroupsReady={setGroups} />
          </Bounds>
        </Suspense>
        {hotspots.map((h) => (
          <Html key={h.region} position={h.position} center distanceFactor={7} zIndexRange={[10, 0]}>
            <div className="anat-hotspot" aria-hidden />
          </Html>
        ))}
        <OrbitControls
          makeDefault
          autoRotate={activeRegions.length === 0}
          autoRotateSpeed={0.5}
          enablePan={false}
          minDistance={0.3}
          maxDistance={8}
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
