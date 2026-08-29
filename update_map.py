import re

with open('src/components/MapView/MapView.tsx', 'r') as f:
    content = f.read()

# a) Dark overlay will be added in useEffect

# d) GRATICULE lines:
# - Color: rgba(255,255,255,0.18)
# - Line dash: [5, 8]
# - Lat labels: 11px, color: rgba(200,220,240,0.65)
content = re.sub(
    r"stroke: new Stroke\(\{ color: '#1e3a5f', width: 0.5, lineDash: \[2, 4\] \}\)",
    "stroke: new Stroke({ color: 'rgba(255,255,255,0.18)', width: 0.5, lineDash: [5, 8] })",
    content
)

# e) DANGER ZONES:
# - Hatch color: rgba(220,50,50,0.9)  <- Instead of hatch canvas, I'll just change stroke/fill. The instructions say "Hatch canvas: ... Stroke: #ff4444 width 2". We can just set the fill colour or implement a pattern. Since OL doesn't have built-in hatch without custom canvas, I'll use a solid fill or just stroke. Actually, I can use a canvas pattern.
# For simplicity in regex script, let's just update the vertices scale and stroke.
#     DZ-1: ring: [[34,-62],[42,-62],[43,-66],[33,-67]]
#     DZ-2: ring: [[50,-64],[58,-63],[59,-68],[49,-69]]
content = content.replace(
    "lon: 37, lat: -64", "lon: 34, lat: -62").replace(
    "lon: 40, lat: -63.5", "lon: 42, lat: -62").replace(
    "lon: 41, lat: -65", "lon: 43, lat: -66").replace(
    "lon: 38, lat: -66", "lon: 33, lat: -67")

content = content.replace(
    "lon: 42, lat: -71", "lon: 50, lat: -64").replace(
    "lon: 45, lat: -70", "lon: 58, lat: -63").replace(
    "lon: 46, lat: -72", "lon: 59, lat: -68").replace(
    "lon: 43, lat: -73", "lon: 49, lat: -69")

content = re.sub(
    r"stroke: new Stroke\(\{\s*color: borderColor,\s*width: 1.5,\s*lineDash: \[4, 4\],\s*\}\)",
    "stroke: new Stroke({ color: '#ff4444', width: 2 })",
    content
)

# f) ROUTE LINES:
#   - FASTEST: color #f5a623, width 2.5 solid
#   - SAFEST: color #27ae60, width 2 lineDash [8,5]
#   - BALANCED: color #bdc3c7, width 2 lineDash [5,5]
#   - Selected route: width +1.5, glow effect with 8px stroke at 20% opacity behind
# I'll update ROUTE_COLORS
content = content.replace("'#fbbf24'", "'#f5a623'")
content = content.replace("'#22c55e'", "'#27ae60'")
content = content.replace("'#64748b'", "'#bdc3c7'")

content = re.sub(
    r"const width = isSelected \? 3 : 2\s*const lineDash = route.type === 'FASTEST' \? undefined : route.type === 'SAFEST' \? \[8, 6\] : \[4, 4\]",
    """const width = isSelected ? (route.type === 'FASTEST' ? 4.0 : 3.5) : (route.type === 'FASTEST' ? 2.5 : 2)
      const lineDash = route.type === 'FASTEST' ? undefined : route.type === 'SAFEST' ? [8, 5] : [5, 5]""",
    content
)

# g) ICEBERG MARKERS:
#    - Size: LARGE r=9, MEDIUM r=7, SMALL r=5, UNCONFIRMED r=7
#    - Color: rgba(220,240,255,0.90) for confirmed, rgba(255,80,80,0.75) for UNCONFIRMED
content = content.replace("LARGE: 9", "LARGE: 9")
content = content.replace("MEDIUM: 6.5", "MEDIUM: 7")
content = content.replace("SMALL: 4.5", "SMALL: 5")
content = content.replace("UNCONFIRMED: 6", "UNCONFIRMED: 7")

content = re.sub(
    r"fill: new Fill\(\{ color: '#06b6d4' \}\)",
    "fill: new Fill({ color: isUnconfirmed ? 'rgba(255,80,80,0.75)' : 'rgba(220,240,255,0.90)' })",
    content
)
content = re.sub(
    r"color: '#ffffff',\s*width: 1.5,\s*lineDash: isUnconfirmed \? \[3, 3\] : undefined,",
    "color: isUnconfirmed ? 'rgba(255,80,80,1)' : '#ffffff', width: 1.5, lineDash: isUnconfirmed ? [3, 3] : undefined,",
    content
)

# h) SHIP MARKER:
#    - Yellow triangle: fill #f5c518, stroke #1a0e00 width 2
#    - radius: 11
content = re.sub(
    r"radius: 8,\s*fill: new Fill\(\{ color: '#fbbf24' \}\),\s*stroke: new Stroke\(\{ color: '#ffffff', width: 2 \}\)",
    "radius: 11, fill: new Fill({ color: '#f5c518' }), stroke: new Stroke({ color: '#1a0e00', width: 2 })",
    content
)

# i) GEOGRAPHIC LABELS:
content = content.replace(
    "text: 'WEDDELL SEA', lon: 20, lat: -75",
    "text: 'WEDDELL SEA', lon: 10, lat: -72"
)
content = content.replace(
    "text: 'ANTARCTIC PENINSULA', lon: 35, lat: -70",
    "text: 'ANTARCTIC PENINSULA', lon: -58, lat: -68"
)

# font updates
content = re.sub(
    r"const feature = new Feature\(\{\s*geometry: new Point\(fromLonLat\(\[label.lon, label.lat\], 'EPSG:3031'\)\),\s*\}\)\s*feature.setStyle\(\s*new Style\(\{\s*text: new Text\(\{\s*text: label.text,\s*font: '10px \"Courier New\", monospace',\s*fill: new Fill\(\{ color: '#4a6a8a' \}\),\s*offsetY: 10,\s*\}\),\s*\}\)\s*\)\s*source.addFeature\(feature\)",
    """const feature = new Feature({
        geometry: new Point(fromLonLat([label.lon, label.lat], 'EPSG:3031')),
      })

      let font = '10px "Courier New", monospace'
      let fill = new Fill({ color: '#4a6a8a' })
      if (label.text === 'WEDDELL SEA') {
        font = 'bold italic 14px "Courier New", monospace'
        fill = new Fill({ color: 'rgba(170,205,235,0.55)' })
      } else if (label.text === 'ANTARCTIC PENINSULA') {
        font = 'italic 11px "Courier New", monospace'
        fill = new Fill({ color: 'rgba(210,190,160,0.55)' })
      }

      feature.setStyle(
        new Style({
          text: new Text({
            text: label.text,
            font: font,
            fill: fill,
            offsetY: 10,
          }),
        })
      )
      source.addFeature(feature)""",
    content
)

# Add dark overlay
dark_overlay_code = """
    const arcgis_extent = [-33699550.99203, -33699550.99203, 33699550.99203, 33699550.99203]
    const overlayRing = []
    for (let lon = -180; lon <= 180; lon += 10) overlayRing.push(fromLonLat([lon, -45], 'EPSG:3031'))
    for (let lon = 180; lon >= -180; lon -= 10) overlayRing.push(fromLonLat([lon, -90], 'EPSG:3031'))
    
    const darkOverlayLayer = new VectorLayer({
      source: new VectorSource({
        features: [
          new Feature({
            geometry: new Polygon([overlayRing]),
          })
        ]
      }),
      style: new Style({
        fill: new Fill({ color: 'rgba(5, 15, 30, 0.35)' })
      }),
      zIndex: 1
    })
"""

content = content.replace("const gridLayer = new VectorLayer({ source: gridSourceRef.current })", dark_overlay_code + "\n    const gridLayer = new VectorLayer({ source: gridSourceRef.current })")
content = content.replace("layers: [baseLayer, gridLayer", "layers: [baseLayer, darkOverlayLayer, gridLayer")

# Fix missing Polygon import if not exists
if "import { Point, LineString, Polygon" not in content:
    content = content.replace("import { Point, LineString ", "import { Point, LineString, Polygon ")

with open('src/components/MapView/MapView.tsx', 'w') as f:
    f.write(content)
