"use client"

import { useEffect, useRef } from "react"
import * as THREE from "three/webgpu"
import { OrbitControls } from "three/addons/controls/OrbitControls.js"

import { loadMola4ppd } from "@/lib/mola-heightmap"
import { buildLocalTerrain, TERRAIN_CELLS } from "@/lib/local-terrain"
import type { MarsCave } from "@/lib/mars-caves"
import { vikingTileUrl } from "@/lib/mars-landing"

export type SiteTerrainProps = {
  lat_deg: number
  lon_east_deg: number
  caves: MarsCave[]
}

export const SiteTerrain = ({
  lat_deg,
  lon_east_deg,
  caves,
}: SiteTerrainProps) => {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) {
      return
    }

    let disposed = false
    let renderer: THREE.WebGPURenderer | null = null
    let controls: OrbitControls | null = null
    let geometry: THREE.BufferGeometry | null = null
    let material: THREE.MeshStandardMaterial | null = null
    let mesh: THREE.Mesh | null = null
    let structureGroup: THREE.Group | null = null
    let albedo: THREE.Texture | null = null

    const initialize = async () => {
      const grid = await loadMola4ppd()
      if (disposed) {
        return
      }

      const terrain = buildLocalTerrain(grid, lat_deg, lon_east_deg, caves)
      const nextRenderer = new THREE.WebGPURenderer({ antialias: true })
      await nextRenderer.init()
      if (disposed) {
        nextRenderer.dispose()
        return
      }

      renderer = nextRenderer
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75))
      renderer.setSize(container.clientWidth, container.clientHeight)
      renderer.setClearColor(0x2a160e, 1)
      container.appendChild(renderer.domElement)
      renderer.domElement.setAttribute("aria-hidden", "true")

      const scene = new THREE.Scene()

      const focus = new THREE.Vector3(
        terrain.habitat.focusX,
        terrain.habitat.focusY,
        terrain.habitat.focusZ,
      )

      const camera = new THREE.PerspectiveCamera(
        52,
        container.clientWidth / container.clientHeight,
        8,
        terrain.spanM * 40,
      )
      camera.position.set(
        focus.x - terrain.spanM * 0.08,
        focus.y + terrain.spanM * 0.11,
        focus.z + terrain.spanM * 0.16,
      )

      geometry = new THREE.PlaneGeometry(
        terrain.spanM,
        terrain.spanM,
        TERRAIN_CELLS,
        TERRAIN_CELLS,
      )
      geometry.setAttribute(
        "position",
        new THREE.BufferAttribute(terrain.positions, 3),
      )
      geometry.setAttribute("color", new THREE.BufferAttribute(terrain.colors, 3))
      geometry.computeVertexNormals()

      try {
        albedo = await new THREE.TextureLoader().loadAsync(
          vikingTileUrl(lat_deg, lon_east_deg, 5),
        )
      } catch {
        albedo = null
      }
      if (disposed) {
        albedo?.dispose()
        renderer.dispose()
        return
      }
      if (albedo) {
        albedo.colorSpace = THREE.SRGBColorSpace
        albedo.anisotropy = 8
      }
      material = new THREE.MeshStandardMaterial({
        map: albedo,
        vertexColors: true,
        roughness: 0.94,
        metalness: 0.02,
        flatShading: false,
        transparent: true,
        opacity: 0.48,
        depthWrite: false,
        side: THREE.DoubleSide,
      })
      mesh = new THREE.Mesh(geometry, material)
      scene.add(mesh)

      structureGroup = new THREE.Group()
      const habMat = new THREE.MeshStandardMaterial({
        color: 0xd8c4a4,
        emissive: 0x2a1e10,
        emissiveIntensity: 0.16,
        roughness: 0.5,
        metalness: 0.06,
      })
      const hubMat = new THREE.MeshStandardMaterial({
        color: 0xfff1cf,
        emissive: 0x7a5a20,
        emissiveIntensity: 0.55,
        roughness: 0.32,
        metalness: 0.1,
      })
      const roomMat = new THREE.MeshStandardMaterial({
        color: 0x3f6f66,
        emissive: 0x0a2a26,
        emissiveIntensity: 0.25,
        roughness: 0.45,
        metalness: 0.04,
        transparent: true,
        opacity: 0.4,
      })
      const bestRoomMat = new THREE.MeshStandardMaterial({
        color: 0x9affea,
        emissive: 0x1ee0b8,
        emissiveIntensity: 1.1,
        roughness: 0.28,
        metalness: 0.08,
        transparent: true,
        opacity: 0.78,
      })
      const shaftMat = new THREE.MeshStandardMaterial({
        color: 0x9aefe0,
        emissive: 0x1c5c50,
        emissiveIntensity: 0.45,
        roughness: 0.4,
        transparent: true,
        opacity: 0.45,
      })
      const tubeMat = new THREE.MeshStandardMaterial({
        color: 0x5cc4b0,
        emissive: 0x0d3a34,
        emissiveIntensity: 0.35,
        roughness: 0.5,
        transparent: true,
        opacity: 0.4,
      })

      for (const box of terrain.habitat.boxes) {
        const building = new THREE.Mesh(
          new THREE.BoxGeometry(box.sx, box.sy, box.sz),
          box.kind === "hub" ? hubMat : habMat,
        )
        building.position.set(box.x, box.y, box.z)
        structureGroup.add(building)
      }

      for (const cave of terrain.caves) {
        const room = new THREE.Mesh(
          new THREE.SphereGeometry(cave.roomRM, 28, 18),
          cave.best ? bestRoomMat : roomMat,
        )
        room.position.set(cave.x, cave.y - cave.depthM, cave.z)
        room.scale.set(1, 0.62, 1.15)
        const shaft = new THREE.Mesh(
          new THREE.CylinderGeometry(
            cave.radiusM * 0.35,
            cave.roomRM * 0.28,
            cave.depthM,
            16,
            1,
            true,
          ),
          shaftMat,
        )
        shaft.position.set(cave.x, cave.y - cave.depthM * 0.5, cave.z)
        const ring = new THREE.Mesh(
          new THREE.RingGeometry(cave.radiusM * 0.28, cave.radiusM * 0.85, 32),
          new THREE.MeshBasicMaterial({
            color: cave.best ? 0xe8fff8 : 0x6a8f88,
            side: THREE.DoubleSide,
            transparent: true,
            opacity: cave.best ? 1 : 0.45,
          }),
        )
        ring.rotation.x = -Math.PI / 2
        ring.position.set(cave.x, cave.y + 40, cave.z)
        structureGroup.add(room)
        structureGroup.add(shaft)
        structureGroup.add(ring)
      }

      const ordered = [...terrain.caves].sort((a, b) => a.x - b.x || a.z - b.z)
      for (let i = 0; i < ordered.length - 1; i += 1) {
        const from = ordered[i]
        const to = ordered[i + 1]
        const start = new THREE.Vector3(
          from.x,
          from.y - from.depthM,
          from.z,
        )
        const end = new THREE.Vector3(to.x, to.y - to.depthM, to.z)
        const delta = end.clone().sub(start)
        const length = delta.length()
        if (length < 80) {
          continue
        }
        const tube = new THREE.Mesh(
          new THREE.CylinderGeometry(
            Math.min(from.roomRM, to.roomRM) * 0.22,
            Math.min(from.roomRM, to.roomRM) * 0.22,
            length,
            12,
          ),
          tubeMat,
        )
        tube.position.copy(start.clone().add(end).multiplyScalar(0.5))
        tube.quaternion.setFromUnitVectors(
          new THREE.Vector3(0, 1, 0),
          delta.normalize(),
        )
        structureGroup.add(tube)
      }
      scene.add(structureGroup)

      const sun = new THREE.DirectionalLight(0xffd2a8, 2.1)
      sun.position.set(terrain.spanM * 0.4, terrain.spanM * 0.8, terrain.spanM * 0.15)
      scene.add(sun)
      scene.add(new THREE.AmbientLight(0x6a4030, 0.85))
      scene.add(new THREE.HemisphereLight(0x6b4a38, 0x2a140c, 0.7))

      const reduceMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)",
      ).matches
      controls = new OrbitControls(camera, renderer.domElement)
      controls.target.copy(focus)
      controls.enableDamping = !reduceMotion
      controls.dampingFactor = 0.08
      controls.maxPolarAngle = Math.PI * 0.9
      controls.minDistance = terrain.spanM * 0.05
      controls.maxDistance = terrain.spanM * 1.6
      controls.update()

      const handleResize = () => {
        if (!renderer || disposed) {
          return
        }
        const width = container.clientWidth
        const height = container.clientHeight
        if (width === 0 || height === 0) {
          return
        }
        camera.aspect = width / height
        camera.updateProjectionMatrix()
        renderer.setSize(width, height)
      }
      window.addEventListener("resize", handleResize)

      renderer.setAnimationLoop(() => {
        if (!renderer || disposed) {
          return
        }
        controls?.update()
        void renderer.render(scene, camera)
      })

      return () => {
        window.removeEventListener("resize", handleResize)
      }
    }

    let detachResize: (() => void) | undefined
    void initialize().then((cleanup) => {
      detachResize = cleanup
    })

    return () => {
      disposed = true
      detachResize?.()
      if (renderer) {
        renderer.setAnimationLoop(null)
        renderer.domElement.remove()
        renderer.dispose()
      }
      controls?.dispose()
      geometry?.dispose()
      material?.dispose()
      albedo?.dispose()
      structureGroup?.traverse((child) => {
        if (child instanceof THREE.Mesh) {
          child.geometry.dispose()
          const childMaterial = child.material
          if (Array.isArray(childMaterial)) {
            childMaterial.forEach((item) => item.dispose())
          } else {
            childMaterial.dispose()
          }
        }
      })
    }
  }, [lat_deg, lon_east_deg, caves])

  return (
    <div className="relative h-full w-full">
      <div
        ref={containerRef}
        className="h-full w-full"
        role="img"
        aria-label="Zoomed Mars terrain with a buried 100-person habitat. Drag to orbit. Scroll to zoom. The ground is faded so the rooms show through."
      />
      <p className="pointer-events-none absolute bottom-3 left-3 max-w-xs text-xs text-stone-400">
        {caves.length > 0
          ? "Bright teal is Annie, the best pit."
          : "Bright box is the habitat hub."}
      </p>
    </div>
  )
}
