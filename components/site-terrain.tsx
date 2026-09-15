"use client"

import { useEffect, useRef } from "react"
import * as THREE from "three/webgpu"
import { OrbitControls } from "three/addons/controls/OrbitControls.js"

import { loadMola4ppd } from "@/lib/mola-heightmap"
import { buildLocalTerrain, TERRAIN_CELLS } from "@/lib/local-terrain"
import { CAVES_CREDIT, type MarsCave } from "@/lib/mars-caves"
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
    let underlay: THREE.Mesh | null = null
    let caveGroup: THREE.Group | null = null
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

      const camera = new THREE.PerspectiveCamera(
        55,
        container.clientWidth / container.clientHeight,
        8,
        terrain.spanM * 40,
      )
      camera.position.set(
        -terrain.spanM * 0.04,
        terrain.spanM * 0.14,
        -terrain.spanM * 0.28,
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
          vikingTileUrl(lat_deg, lon_east_deg, 4),
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
      })
      mesh = new THREE.Mesh(geometry, material)
      scene.add(mesh)

      underlay = new THREE.Mesh(
        new THREE.CircleGeometry(terrain.spanM * 3, 64),
        new THREE.MeshStandardMaterial({
          color: 0x4a2414,
          roughness: 1,
          metalness: 0,
        }),
      )
      underlay.rotation.x = -Math.PI / 2
      underlay.position.y = -terrain.spanM * 0.01
      scene.add(underlay)

      caveGroup = new THREE.Group()
      for (const cave of terrain.caves) {
        const ring = new THREE.Mesh(
          new THREE.RingGeometry(cave.radiusM * 0.55, cave.radiusM, 36),
          new THREE.MeshBasicMaterial({
            color: 0x7de0c6,
            side: THREE.DoubleSide,
            transparent: true,
            opacity: 0.9,
          }),
        )
        ring.rotation.x = -Math.PI / 2
        ring.position.set(cave.x, cave.y, cave.z)
        const beam = new THREE.Mesh(
          new THREE.CylinderGeometry(cave.radiusM * 0.12, cave.radiusM * 0.12, cave.radiusM * 1.4, 10),
          new THREE.MeshBasicMaterial({
            color: 0x7de0c6,
            transparent: true,
            opacity: 0.35,
          }),
        )
        beam.position.set(cave.x, cave.y + cave.radiusM * 0.5, cave.z)
        caveGroup.add(ring)
        caveGroup.add(beam)
      }
      scene.add(caveGroup)

      const sun = new THREE.DirectionalLight(0xffd2a8, 2.1)
      sun.position.set(terrain.spanM * 0.4, terrain.spanM * 0.8, terrain.spanM * 0.15)
      scene.add(sun)
      scene.add(new THREE.AmbientLight(0x6a4030, 0.55))
      scene.add(new THREE.HemisphereLight(0x6b4a38, 0x2a140c, 0.45))

      const reduceMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)",
      ).matches
      controls = new OrbitControls(camera, renderer.domElement)
      controls.target.set(0, 0, 0)
      controls.enableDamping = !reduceMotion
      controls.dampingFactor = 0.08
      controls.maxPolarAngle = Math.PI / 2.08
      controls.minDistance = terrain.spanM * 0.06
      controls.maxDistance = terrain.spanM * 2.4
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
      if (underlay) {
        underlay.geometry.dispose()
        const underlayMaterial = underlay.material
        if (Array.isArray(underlayMaterial)) {
          underlayMaterial.forEach((item) => item.dispose())
        } else {
          underlayMaterial.dispose()
        }
      }
      caveGroup?.traverse((child) => {
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
        aria-label="Zoomed Mars terrain. Drag to orbit. Scroll to zoom."
      />
      {caves.length > 0 ? (
        <p className="pointer-events-none absolute bottom-3 left-3 max-w-sm text-xs text-stone-400">
          Teal rings are THEMIS cave pits. {CAVES_CREDIT}
        </p>
      ) : null}
    </div>
  )
}
