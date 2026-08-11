(function () {
  'use strict'
  var root = null
  var view = null
  var surface = null

  function presetValue(preset, x, y) {
    if (preset === 'ripple') return Math.sin(x * x + y * y) / (1 + 0.12 * (x * x + y * y))
    if (preset === 'saddle') return 0.22 * (x * x - y * y)
    if (preset === 'gaussian') return 2.2 * Math.exp(-0.35 * (x * x + y * y))
    return Math.sin(x) * Math.cos(y)
  }

  function sampledValue(scene, x, y) {
    var grid = scene.sampleGrid
    if (!grid) return presetValue(scene.preset, x, y)
    var gx = Math.max(0, Math.min(grid.resolution - 1, (x + grid.range) / (grid.range * 2) * (grid.resolution - 1)))
    var gy = Math.max(0, Math.min(grid.resolution - 1, (y + grid.range) / (grid.range * 2) * (grid.resolution - 1)))
    var x0 = Math.floor(gx); var y0 = Math.floor(gy)
    var x1 = Math.min(grid.resolution - 1, x0 + 1); var y1 = Math.min(grid.resolution - 1, y0 + 1)
    var tx = gx - x0; var ty = gy - y0
    function at(column, row) { return grid.values[row * grid.resolution + column] || 0 }
    return at(x0, y0) * (1 - tx) * (1 - ty) + at(x1, y0) * tx * (1 - ty) + at(x0, y1) * (1 - tx) * ty + at(x1, y1) * tx * ty
  }

  function initialize() {
    try {
      if (!window.MathBox || !window.THREE || !window.THREE.OrbitControls) throw new Error('Compatibility libraries did not initialize.')
      root = window.MathBox.mathBox({ element: document.getElementById('stage'), plugins: ['core', 'controls', 'cursor'], controls: { klass: window.THREE.OrbitControls }, camera: { fov: 42 } })
      if (root.three && root.three.renderer) root.three.renderer.setClearColor(0x090d11, 1)
      view = root.cartesian({ range: [[-5, 5], [-3, 3], [-5, 5]], scale: [1, 0.65, 1] })
      view.axis({ axis: 1, color: 0x8a949f, width: 2 }); view.axis({ axis: 2, color: 0x8a949f, width: 2 }); view.axis({ axis: 3, color: 0x8a949f, width: 2 })
      view.grid({ axes: [1, 3], color: 0x303840, width: 1, divideX: 10, divideY: 10 })
      parent.postMessage({ type: 'mathbox-ready' }, location.origin)
    } catch (error) { parent.postMessage({ type: 'mathbox-error', message: error.message }, location.origin) }
  }

  window.addEventListener('message', function (event) {
    if (event.origin !== location.origin || event.source !== parent) return
    try {
      if (event.data.type === 'mathbox-scene' && view) {
        if (surface) surface.remove()
        var scene = event.data.scene
        var color = parseInt(event.data.accent.replace('#', ''), 16)
        surface = view.area({ axes: [1, 3], width: event.data.resolution, height: event.data.resolution, expr: function (emit, x, y) { emit(x, sampledValue(scene, x, y), y) } }).surface({ color: color, shaded: !scene.wireframe, fill: !scene.wireframe, lineX: scene.wireframe, lineY: scene.wireframe, width: 1.2 })
      } else if (event.data.type === 'mathbox-resize') window.dispatchEvent(new Event('resize'))
      else if (event.data.type === 'mathbox-pause') document.getElementById('stage').style.visibility = 'hidden'
      else if (event.data.type === 'mathbox-resume') document.getElementById('stage').style.visibility = ''
      else if (event.data.type === 'mathbox-dispose' && root && root.three && root.three.destroy) root.three.destroy()
    } catch (error) { parent.postMessage({ type: 'mathbox-error', message: error.message }, location.origin) }
  })
  window.addEventListener('pagehide', function () { if (root && root.three && root.three.destroy) root.three.destroy() })
  window.addEventListener('DOMContentLoaded', initialize)
}())
