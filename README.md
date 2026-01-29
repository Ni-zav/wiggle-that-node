# Wiggle That Node

Blender 4.2+ extension that disconnects nodes when you wiggle them aggressively.

## What It Does

Select a node in any node editor and wiggle it back and forth rapidly - boom, all connections drop.

Works in:
- Shader Editor
- Compositor
- Geometry Nodes
- World nodes
- Any other node editor

## Install

1. Download the releases, drag and drop (or on the preferences > extensions > install from disk)

## Use

1. Open a Node Editor
2. Go to the **Wiggle** sidebar tab (right panel, press N if hidden)
3. Toggle **Wiggle Detection ON**
4. Select a node and wiggle it → it disconnects

## Settings

**Sensitivity Presets**
- **Low** - needs aggressive wiggling
- **Medium** - default, balanced
- **High** - even gentle shaking triggers it

**Advanced**
- `Time Window` - how long to track (seconds)
- `Direction Changes` - reversals needed to disconnect
- `Wiggle Ratio` - movement vs displacement threshold
- `Min Movement` - minimum pixels to register
- `Min Total Distance` - total distance before trigger

## Quick Tips

- Enable in the header button (checkbox icon) or sidebar
- Manually disconnect any selected nodes with the "Disconnect Selected Nodes" button
- Tweak sensitivity if it's too eager or not responsive enough
- Works with multi-node selections if enabled

## How It Works

Tracks node positions and detects:
1. Rapid back-and-forth movement
2. Multiple direction reversals
3. High movement-to-displacement ratio (the "wiggle" signature)

When all conditions met → disconnects all links to that node.

---

Made for people who accidentally drag nodes into spaghetti node trees and want a quick way out.
