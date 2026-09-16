"use client"

import { useEffect, useRef, useState } from "react"
import {
  CameraEventType,
  Cartesian2,
  Cartesian3,
  Cartographic,
  Color,
  CustomHeightmapTerrainProvider,
  Ellipsoid,
  GeographicProjection,
  GeographicTilingScheme,
  HeightReference,
  ImageryLayer,
  KeyboardEventModifier,
  Math as CesiumMath,
  Rectangle,
  SceneMode,
  SceneTransforms,
  ScreenSpaceCameraController,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  SkyAtmosphere,
  UrlTemplateImageryProvider,
  Viewer,
} from "cesium"
import "cesium/Build/Cesium/Widgets/widgets.css"

import { SiteMark } from "@/components/site-mark"
import { loadMola4ppd, sampleMolaBilinear } from "@/lib/mola-heightmap"
import {
  caveDistanceDeg,
  caveEntityId,
  BEST_CAVE_ID,
  caveFact,
  caveIdFromEntity,
  pinDistanceDeg,
  MARS_CAVES,
} from "@/lib/mars-caves"
import {
  BEST_SITE_ID,
  NASA_AREA_BY_ID,
  type NasaAreaRole,
} from "@/lib/nasa-areas"
import {
  customSiteHref,
  lon180ToEast,
  lonEastTo180,
  shortSiteName,
  siteHref,
  type CustomSite,
  type LandingPick,
  type LandingSite,
} from "@/lib/mars-landing"

export type MarsGlobeProps = {
  pick: LandingPick
  sites: LandingSite[]
  customSites: CustomSite[]
  onPick: (next: LandingPick) => void
  onCustomAdd: (lat_deg: number, lon_east_deg: number) => void
  onReady?: () => void
  onFail?: () => void
}

const TILE = 65
const EXAGGERATION = 10
const SITE_HEIGHT_M = 400
const LONG_PRESS_MS = 700
const HIT_PX = 44
const WORLD_RECTANGLE = Rectangle.fromDegrees(-180, -72, 180, 72)

type ScreenMark = {
  id: string
  name: string
  x: number
  y: number
  href: string
  fact: string
  lat_deg: number
  lon_east_deg: number
  role: NasaAreaRole | "custom"
  compact?: boolean
  recommended?: boolean
}
const VIKING_TILES =
  "https://trek.nasa.gov/tiles/Mars/EQ/Mars_Viking_MDIM21_ClrMosaic_global_232m/1.0.0/default/default028mm/{z}/{y}/{x}.jpg"

const applyEarthNavigation = (cameraControl: ScreenSpaceCameraController) => {
  cameraControl.enableZoom = true
  cameraControl.enableTilt = true
  cameraControl.enableRotate = true
  cameraControl.enableTranslate = true
  cameraControl.enableLook = false
  cameraControl.enableCollisionDetection = true
  cameraControl.zoomFactor = 12
  cameraControl.inertiaZoom = 0.82
  cameraControl.inertiaSpin = 0.88
  cameraControl.inertiaTranslate = 0.86
  cameraControl.minimumZoomDistance = 80
  cameraControl.maximumZoomDistance = 4.5e7
  cameraControl.minimumCollisionTerrainHeight = 400
  cameraControl.minimumPickingTerrainHeight = 200
  cameraControl.maximumTiltAngle = CesiumMath.PI_OVER_TWO
  cameraControl.translateEventTypes = [CameraEventType.LEFT_DRAG]
  cameraControl.zoomEventTypes = [
    CameraEventType.WHEEL,
    CameraEventType.PINCH,
    CameraEventType.RIGHT_DRAG,
  ]
  cameraControl.tiltEventTypes = [
    CameraEventType.PINCH,
    CameraEventType.MIDDLE_DRAG,
    {
      eventType: CameraEventType.LEFT_DRAG,
      modifier: KeyboardEventModifier.SHIFT,
    },
    {
      eventType: CameraEventType.WHEEL,
      modifier: KeyboardEventModifier.SHIFT,
    },
  ]
  cameraControl.rotateEventTypes = [
    {
      eventType: CameraEventType.LEFT_DRAG,
      modifier: KeyboardEventModifier.CTRL,
    },
  ]
}

const pickLatLon = (viewer: Viewer, position: Cartesian2) => {
  const ray = viewer.camera.getPickRay(position)
  if (!ray) {
    return undefined
  }
  const cartesian = viewer.scene.globe.pick(ray, viewer.scene)
  if (!cartesian) {
    return undefined
  }
  const carto = Cartographic.fromCartesian(cartesian)
  return {
    lat_deg: CesiumMath.toDegrees(carto.latitude),
    lon_east_deg: lon180ToEast(CesiumMath.toDegrees(carto.longitude)),
  }
}

const addTooltip = (
  viewer: Viewer,
  id: string,
  name: string,
  lat: number,
  lonEast: number,
  selected: boolean,
  kind: "nasa" | "custom" | "cave",
) => {
  const fill =
    kind === "cave"
      ? "#7de0c6"
      : selected
        ? "#fff6ea"
        : kind === "custom"
          ? "#f4c38a"
          : "#e8b48a"
  viewer.entities.add({
    id,
    name,
    position: Cartesian3.fromDegrees(lonEastTo180(lonEast), lat, SITE_HEIGHT_M),
    point: {
      pixelSize: selected ? 14 : kind === "cave" ? 6 : 10,
      color: Color.fromCssColorString(fill),
      outlineColor: Color.BLACK,
      outlineWidth: 1,
      heightReference: HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },
  })
}

const syncEntities = (
  viewer: Viewer,
  sites: LandingSite[],
  customSites: CustomSite[],
  pick: LandingPick,
) => {
  viewer.entities.removeAll()
  for (const site of sites) {
    const selected = pick.siteId === site.id
    const lon = lonEastTo180(site.lon_east_deg)
    const area = NASA_AREA_BY_ID[site.id]
    if (area) {
      viewer.entities.add({
        id: `area-${site.id}`,
        name: site.name,
        position: Cartesian3.fromDegrees(lon, site.lat_deg),
        ellipse: {
          semiMajorAxis: area.ellipseKm[0] * 500,
          semiMinorAxis: area.ellipseKm[1] * 500,
          rotation: CesiumMath.toRadians(area.headingDeg),
          material: Color.fromCssColorString("#f4d7a8").withAlpha(
            selected ? 0.28 : 0.1,
          ),
          height: 0,
          heightReference: HeightReference.CLAMP_TO_GROUND,
        },
      })
    }
    addTooltip(
      viewer,
      site.id,
      shortSiteName(site.name),
      site.lat_deg,
      site.lon_east_deg,
      selected,
      "nasa",
    )
  }

  for (const site of customSites) {
    addTooltip(
      viewer,
      site.id,
      "Custom",
      site.lat_deg,
      site.lon_east_deg,
      pick.siteId === site.id,
      "custom",
    )
  }

  for (const cave of MARS_CAVES) {
    addTooltip(
      viewer,
      caveEntityId(cave.id),
      cave.name,
      cave.lat_deg,
      cave.lon_east_deg,
      caveDistanceDeg(cave, pick.lat_deg, pick.lon_east_deg) < 0.08,
      "cave",
    )
  }
}

const entitySiteId = (
  raw: unknown,
  sites: LandingSite[],
  customSites: CustomSite[],
) => {
  if (!raw || typeof raw !== "object" || !("id" in raw)) {
    return undefined
  }
  const id = String((raw as { id: string }).id)
  if (id.startsWith("area-")) {
    return id.slice(5)
  }
  if (id.startsWith("cave-")) {
    return id
  }
  if (sites.some((site) => site.id === id)) {
    return id
  }
  if (customSites.some((site) => site.id === id)) {
    return id
  }
  return undefined
}

const siteAtScreen = (
  viewer: Viewer,
  position: Cartesian2,
  sites: LandingSite[],
  customSites: CustomSite[],
) => {
  const picked = viewer.scene.pick(position, HIT_PX, HIT_PX)
  const pickedId =
    picked && typeof picked === "object" && "id" in picked
      ? entitySiteId(picked.id, sites, customSites)
      : undefined
  if (pickedId) {
    return pickedId
  }

  let nearest: { id: string; dist: number } | undefined
  const consider = (id: string, lat: number, lonEast: number) => {
    const cartesian = Cartesian3.fromDegrees(
      lonEastTo180(lonEast),
      lat,
      SITE_HEIGHT_M,
    )
    const win = SceneTransforms.worldToWindowCoordinates(viewer.scene, cartesian)
    if (!win) {
      return
    }
    const dist = Math.hypot(win.x - position.x, win.y - position.y)
    if (dist > HIT_PX) {
      return
    }
    if (!nearest || dist < nearest.dist) {
      nearest = { id, dist }
    }
  }
  for (const site of sites) {
    consider(site.id, site.lat_deg, site.lon_east_deg)
  }
  for (const site of customSites) {
    consider(site.id, site.lat_deg, site.lon_east_deg)
  }
  for (const cave of MARS_CAVES) {
    consider(caveEntityId(cave.id), cave.lat_deg, cave.lon_east_deg)
  }
  return nearest?.id
}

export const MarsGlobe = ({
  pick,
  sites,
  customSites,
  onPick,
  onCustomAdd,
  onReady,
  onFail,
}: MarsGlobeProps) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)
  const pickRef = useRef(pick)
  const sitesRef = useRef(sites)
  const customRef = useRef(customSites)
  const onPickRef = useRef(onPick)
  const onCustomAddRef = useRef(onCustomAdd)
  const onReadyRef = useRef(onReady)
  const onFailRef = useRef(onFail)
  const viewerRef = useRef<Viewer | null>(null)
  const marksKeyRef = useRef("")
  const [marks, setMarks] = useState<ScreenMark[]>([])

  const publishMarks = () => {
    const viewer = viewerRef.current
    const overlay = overlayRef.current
    if (!viewer || viewer.isDestroyed() || !overlay) {
      return
    }
    const canvas = viewer.scene.canvas
    const canvasBox = canvas.getBoundingClientRect()
    const overlayBox = overlay.getBoundingClientRect()
    const offsetX = canvasBox.left - overlayBox.left
    const offsetY = canvasBox.top - overlayBox.top
    const next: ScreenMark[] = []
    const push = (
      id: string,
      name: string,
      lat: number,
      lonEast: number,
      href: string,
      fact: string,
      role: NasaAreaRole | "custom",
    ) => {
      const cartesian = Cartesian3.fromDegrees(
        lonEastTo180(lonEast),
        lat,
        SITE_HEIGHT_M,
      )
      const win = SceneTransforms.worldToWindowCoordinates(
        viewer.scene,
        cartesian,
      )
      if (!win) {
        return
      }
      const x = win.x + offsetX
      const y = win.y + offsetY
      if (
        x < -80 ||
        y < -40 ||
        x > overlay.clientWidth + 80 ||
        y > overlay.clientHeight + 40
      ) {
        return
      }
      next.push({
        id,
        name,
        x,
        y,
        href,
        fact,
        lat_deg: lat,
        lon_east_deg: lonEast,
        role,
        recommended:
          id === BEST_SITE_ID || id === caveEntityId(BEST_CAVE_ID),
      })
    }
    for (const site of sitesRef.current) {
      const area = NASA_AREA_BY_ID[site.id]
      push(
        site.id,
        shortSiteName(site.name),
        site.lat_deg,
        site.lon_east_deg,
        siteHref(site.id),
        area?.source ?? site.why_it_matters,
        area?.role ?? "shortlist",
      )
    }
    for (const site of customRef.current) {
      push(
        site.id,
        "Custom",
        site.lat_deg,
        site.lon_east_deg,
        customSiteHref(site.lat_deg, site.lon_east_deg),
        "Dropped with a long-press. Not a NASA ellipse.",
        "custom",
      )
    }
    for (const cave of MARS_CAVES) {
      push(
        caveEntityId(cave.id),
        cave.name,
        cave.lat_deg,
        cave.lon_east_deg,
        customSiteHref(cave.lat_deg, cave.lon_east_deg),
        caveFact(cave),
        "cave_shelter",
      )
    }
    const caveMarks = next.filter((mark) => mark.role === "cave_shelter")
    const cavesClustered = caveMarks.some((left, index) =>
      caveMarks.some(
        (right, other) =>
          index < other && Math.hypot(left.x - right.x, left.y - right.y) < 36,
      ),
    )
    if (cavesClustered) {
      for (const mark of next) {
        if (mark.role === "cave_shelter" && !mark.recommended) {
          mark.compact = true
        }
      }
    }
    const key = next
      .map(
        (mark) =>
          `${mark.id}:${Math.round(mark.x)}:${Math.round(mark.y)}:${mark.compact ? "c" : "n"}`,
      )
      .join("|")
    if (key === marksKeyRef.current) {
      return
    }
    marksKeyRef.current = key
    setMarks(next)
  }

  useEffect(() => {
    pickRef.current = pick
    sitesRef.current = sites
    customRef.current = customSites
    onPickRef.current = onPick
    onCustomAddRef.current = onCustomAdd
    onReadyRef.current = onReady
    onFailRef.current = onFail
  }, [pick, sites, customSites, onPick, onCustomAdd, onReady, onFail])

  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || viewer.isDestroyed()) {
      return
    }
    syncEntities(viewer, sites, customSites, pick)
    publishMarks()
  }, [pick, sites, customSites])

  useEffect(() => {
    const container = containerRef.current
    if (!container) {
      return
    }

    let disposed = false
    let viewer: Viewer | null = null

    const initialize = async () => {
      try {
        window.CESIUM_BASE_URL = "/cesium/"
        Ellipsoid.default = Ellipsoid.MARS

        const grid = await loadMola4ppd()
        if (disposed) {
          return
        }

        const tilingScheme = new GeographicTilingScheme({
          ellipsoid: Ellipsoid.MARS,
          numberOfLevelZeroTilesX: 2,
          numberOfLevelZeroTilesY: 1,
        })

        const terrainProvider = new CustomHeightmapTerrainProvider({
          width: TILE,
          height: TILE,
          tilingScheme,
          ellipsoid: Ellipsoid.MARS,
          credit: "MOLA MEGDR 4 ppd · NASA / GSFC",
          callback: (x, y, level) => {
            const rectangle = tilingScheme.tileXYToRectangle(x, y, level)
            const heights = new Float32Array(TILE * TILE)
            for (let row = 0; row < TILE; row += 1) {
              const lat = CesiumMath.toDegrees(
                rectangle.north -
                  (rectangle.north - rectangle.south) * (row / (TILE - 1)),
              )
              for (let col = 0; col < TILE; col += 1) {
                const lon180 = CesiumMath.toDegrees(
                  rectangle.west +
                    (rectangle.east - rectangle.west) * (col / (TILE - 1)),
                )
                heights[row * TILE + col] = sampleMolaBilinear(
                  grid,
                  lat,
                  lon180ToEast(lon180),
                )
              }
            }
            return heights
          },
        })

        const trek = new UrlTemplateImageryProvider({
          url: VIKING_TILES,
          tilingScheme,
          minimumLevel: 0,
          maximumLevel: 7,
          tileWidth: 256,
          tileHeight: 256,
          credit: "Viking MDIM 2.1 232 m · NASA Trek / USGS",
        })

        viewer = new Viewer(container, {
          animation: false,
          timeline: false,
          geocoder: false,
          baseLayerPicker: false,
          fullscreenButton: false,
          vrButton: false,
          infoBox: false,
          selectionIndicator: false,
          homeButton: true,
          sceneModePicker: false,
          projectionPicker: false,
          navigationHelpButton: true,
          navigationInstructionsInitiallyVisible: false,
          ellipsoid: Ellipsoid.MARS,
          terrainProvider,
          mapProjection: new GeographicProjection(Ellipsoid.MARS),
          baseLayer: new ImageryLayer(trek),
          skyAtmosphere: new SkyAtmosphere(Ellipsoid.MARS),
          sceneMode: SceneMode.COLUMBUS_VIEW,
          msaaSamples: 4,
          useBrowserRecommendedResolution: true,
          requestRenderMode: false,
        })
        if (disposed) {
          viewer.destroy()
          return
        }

        viewer.scene.globe.baseColor = Color.fromCssColorString("#8a3a1c")
        viewer.scene.globe.enableLighting = false
        viewer.scene.globe.depthTestAgainstTerrain = true
        viewer.scene.verticalExaggeration = EXAGGERATION
        viewer.scene.verticalExaggerationRelativeHeight = 0
        viewer.scene.backgroundColor = Color.fromCssColorString("#140c08")
        viewer.resolutionScale = 1

        applyEarthNavigation(viewer.scene.screenSpaceCameraController)

        viewerRef.current = viewer
        syncEntities(viewer, sitesRef.current, customRef.current, pickRef.current)
        viewer.camera.percentageChanged = 0.01
        viewer.camera.changed.addEventListener(publishMarks)
        viewer.scene.postRender.addEventListener(publishMarks)
        publishMarks()

        const handler = new ScreenSpaceEventHandler(viewer.scene.canvas)
        let pressTimer: number | undefined
        let pressStart: Cartesian2 | undefined
        let didLongPress = false

        const clearPress = () => {
          if (pressTimer !== undefined) {
            window.clearTimeout(pressTimer)
            pressTimer = undefined
          }
          pressStart = undefined
        }

        const selectEntityAt = (position: Cartesian2) => {
          const current = viewer
          if (!current || current.isDestroyed()) {
            return false
          }
          const pickedId = siteAtScreen(
            current,
            position,
            sitesRef.current,
            customRef.current,
          )
          if (!pickedId) {
            return false
          }
          const caveId = caveIdFromEntity(pickedId)
          const cave = caveId
            ? MARS_CAVES.find((item) => item.id === caveId)
            : undefined
          if (cave) {
            onPickRef.current({
              lat_deg: cave.lat_deg,
              lon_east_deg: cave.lon_east_deg,
              siteId: "custom",
            })
            return true
          }
          const nasa = sitesRef.current.find((item) => item.id === pickedId)
          if (nasa) {
            onPickRef.current({
              lat_deg: nasa.lat_deg,
              lon_east_deg: nasa.lon_east_deg,
              siteId: nasa.id,
            })
            return true
          }
          const custom = customRef.current.find((item) => item.id === pickedId)
          if (custom) {
            onPickRef.current({
              lat_deg: custom.lat_deg,
              lon_east_deg: custom.lon_east_deg,
              siteId: custom.id,
            })
            return true
          }
          return false
        }

        handler.setInputAction((down: { position: Cartesian2 }) => {
          const current = viewer
          if (!current || current.isDestroyed()) {
            return
          }
          didLongPress = false
          pressStart = Cartesian2.clone(down.position)
          if (
            siteAtScreen(
              current,
              down.position,
              sitesRef.current,
              customRef.current,
            )
          ) {
            return
          }
          pressTimer = window.setTimeout(() => {
            const start = pressStart
            pressTimer = undefined
            if (!start || current.isDestroyed()) {
              return
            }
            if (
              siteAtScreen(
                current,
                start,
                sitesRef.current,
                customRef.current,
              )
            ) {
              return
            }
            const at = pickLatLon(current, start)
            if (!at) {
              return
            }
            didLongPress = true
            onCustomAddRef.current(at.lat_deg, at.lon_east_deg)
          }, LONG_PRESS_MS)
        }, ScreenSpaceEventType.LEFT_DOWN)

        handler.setInputAction((move: { startPosition: Cartesian2; endPosition: Cartesian2 }) => {
          if (!pressStart) {
            return
          }
          const dx = move.endPosition.x - pressStart.x
          const dy = move.endPosition.y - pressStart.y
          if (Math.hypot(dx, dy) > 8) {
            clearPress()
          }
        }, ScreenSpaceEventType.MOUSE_MOVE)

        handler.setInputAction(() => {
          clearPress()
        }, ScreenSpaceEventType.LEFT_UP)

        handler.setInputAction(() => {
          clearPress()
        }, ScreenSpaceEventType.PINCH_START)

        handler.setInputAction((click: { position: Cartesian2 }) => {
          if (didLongPress) {
            didLongPress = false
            return
          }
          selectEntityAt(click.position)
        }, ScreenSpaceEventType.LEFT_CLICK)

        viewer.camera.setView({
          destination: WORLD_RECTANGLE,
        })
        onReadyRef.current?.()
      } catch {
        onFailRef.current?.()
      }
    }

    void initialize()

    return () => {
      disposed = true
      viewerRef.current = null
      if (viewer && !viewer.isDestroyed()) {
        viewer.destroy()
      }
    }
  }, [])

  return (
    <div className="cesium-mars relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />
      <div ref={overlayRef} className="pointer-events-none fixed inset-0 z-20">
        {marks.map((mark) => (
          <SiteMark
            key={mark.id}
            href={mark.href}
            name={mark.name}
            lat_deg={mark.lat_deg}
            lon_east_deg={mark.lon_east_deg}
            fact={mark.fact}
            role={mark.role}
            compact={mark.compact}
            recommended={mark.recommended}
            selected={
              mark.role === "cave_shelter"
                ? pinDistanceDeg(
                    mark.lat_deg,
                    mark.lon_east_deg,
                    pick.lat_deg,
                    pick.lon_east_deg,
                  ) < 0.08
                : pick.siteId === mark.id
            }
            className="absolute -translate-x-1/2 -translate-y-[calc(100%+6px)]"
            style={{ left: mark.x, top: mark.y }}
          />
        ))}
      </div>
    </div>
  )
}

declare global {
  interface Window {
    CESIUM_BASE_URL?: string
  }
}
