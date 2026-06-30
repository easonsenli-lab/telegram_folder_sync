# RosePay luxury fintech landing page

This project is an ultra-premium, high-converting **Luxury Fintech** landing page for **RosePay**, designed with space earth visualizations, a golden highlighted boundary map of India, and floating golden rose brand elements.

---

## 🚀 Getting Started

To run the project locally on your system, execute the following commands in the workspace directory:

### 1. Install Dependencies
```bash
npm install
```

### 2. Start Local Development Server
```bash
npm run dev
```
The application will launch on the local port (usually `http://localhost:5173`).

### 3. Build for Production
```bash
npm run build
```

---

## 🎨 Content Configuration & Editing Copy

All visual texts, numbers, links, and values are externalized to a single configuration file for easy maintenance:
👉 **[src/data/content.ts](file:///e:/RosePay_workspace/src/data/content.ts)**

Open this file to customize:
*   **Brand Text**: Edit `siteConfig.brandName` / `siteConfig.logoText`.
*   **Hero Headers**: Modify `siteConfig.hero.titleLines` or `siteConfig.hero.subtitle`.
*   **Odometer Metrics**: Update the vertical indicators array under `siteConfig.metrics` (e.g., "Countries & Regions", "Financial Institutions", etc.).
*   **Core Capabilities**: Adjust title and description pairs under `siteConfig.capabilities`.
*   **Newsletter Text**: Update form placeholders and success messages in `siteConfig.contact`.

---

## 🌹 Asset Replacement Guide

### 1. How to Replace the Logo
The logo is rendered as a clean, lightweight inline vector SVG in the Header component:
👉 **[src/components/Header.tsx](file:///e:/RosePay_workspace/src/components/Header.tsx)**

To replace the logo:
*   Open `Header.tsx`, locate the `<!-- Logo -->` block.
*   Swap out the SVG path with your brand's vector SVG code, or replace the `<svg>` node with an `<img>` tag pointing to your image asset:
    ```tsx
    <img src="/assets/my-new-logo.svg" alt="RosePay Logo" className="w-8 h-8" />
    ```

### 2. How to Replace the Golden Rose
The rose is designed as a highly reflective luxury golden metal vector SVG layer inside the GoldenRose component:
👉 **[src/components/GoldenRose.tsx](file:///e:/RosePay_workspace/src/components/GoldenRose.tsx)**

To replace this with an custom PNG image or 3D object:
*   **To swap with a high-res PNG image**: Put your image in the `public/assets/` directory, open `GoldenRose.tsx`, and replace the `<svg>` tag with your image:
    ```tsx
    <img
      src="/assets/gold-rose.webp"
      alt="Golden Rose Art"
      className="w-[85%] h-[85%] object-contain drop-shadow-[0_10px_35px_rgba(217,164,65,0.45)] group-hover:scale-105 transition-all duration-700"
    />
    ```
*   **To swap with a 3D model (Three.js / React Three Fiber)**: Refer to the Three.js Hooking section below.

---

## 🌐 How to integrate Advanced Three.js / Spline Animations

To upgrade the static Canvas/SVG earth or 3D rose to interactive 3D models using React Three Fiber, follow these steps:

### 1. Install Three.js Dev Dependencies
Install the required React Three Fiber libraries:
```bash
npm install three @types/three @react-three/fiber @react-three/drei
```

### 2. Replace EarthNetwork with a 3D Globe
Create a new 3D Globe canvas in **[src/components/EarthNetwork.tsx](file:///e:/RosePay_workspace/src/components/EarthNetwork.tsx)**:
```tsx
import React from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';

export default function EarthNetwork() {
  return (
    <div className="absolute top-0 right-0 w-full h-full -z-10 opacity-70">
      <Canvas camera={{ position: [0, 0, 3] }}>
        <ambientLight intensity={0.5} />
        <pointLight position={[10, 10, 10]} intensity={1.5} color="#FFD88A" />
        <mesh rotation={[0.1, 0.2, 0]}>
          <sphereGeometry args={[1.2, 32, 32]} />
          <meshStandardMaterial color="#040711" roughness={0.4} metalness={0.8} />
        </mesh>
        <OrbitControls enableZoom={false} autoRotate autoRotateSpeed={0.5} />
      </Canvas>
    </div>
  );
}
```

### 3. Load a 3D Golden Rose GLTF Model
Create a 3D model loader inside **[src/components/GoldenRose.tsx](file:///e:/RosePay_workspace/src/components/GoldenRose.tsx)**:
```tsx
import React, { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { useGLTF, PresentationControls } from '@react-three/drei';

function RoseModel() {
  // Load model from public directory (gltf/glb)
  const { scene } = useGLTF('/assets/golden_rose.glb');
  return <primitive object={scene} scale={1.8} position={[0, -0.5, 0]} />;
}

export default function GoldenRose() {
  return (
    <div className="relative w-80 h-80">
      <Canvas>
        <ambientLight intensity={0.3} />
        <directionalLight position={[5, 5, 5]} color="#FFD88A" intensity={2} />
        <PresentationControls global config={{ mass: 2, tension: 500 }} snap={{ mass: 4, tension: 1500 }}>
          <Suspense fallback={null}>
            <RoseModel />
          </Suspense>
        </PresentationControls>
      </Canvas>
    </div>
  );
}
```
