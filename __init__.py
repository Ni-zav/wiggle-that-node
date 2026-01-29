"""
Wiggle That Node - Blender Extension
Detach nodes from their connections by wiggling them aggressively.
Works with all node types: Shader, Compositor, World, Geometry Nodes, etc.
"""

import bpy
import time
from collections import defaultdict
from mathutils import Vector


# Store movement history per node
class WiggleTracker:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.positions = {}  # node_name -> list of (time, position) tuples
        self.last_check = {}  # node_name -> last check time
        self.direction_changes = {}  # node_name -> count of direction changes
        self.last_direction = {}  # node_name -> last movement direction
        self.wiggle_start_time = {}  # node_name -> when wiggle detection started


tracker = WiggleTracker()


def get_node_tree(context):
    """Get the active node tree from context."""
    space = context.space_data
    if not space or space.type != 'NODE_EDITOR':
        return None
    
    # Get the node tree being edited
    tree = space.edit_tree
    return tree


def disconnect_node(node_tree, node):
    """Remove all links connected to the given node."""
    links_to_remove = []
    
    for link in node_tree.links:
        if link.from_node == node or link.to_node == node:
            links_to_remove.append(link)
    
    for link in links_to_remove:
        node_tree.links.remove(link)
    
    return len(links_to_remove)


def detect_wiggle(node_name, current_pos, settings):
    """
    Detect if a node is being wiggled based on rapid direction changes.
    Returns True if wiggle is detected.
    """
    current_time = time.time()
    
    # Initialize tracking for new nodes
    if node_name not in tracker.positions:
        tracker.positions[node_name] = []
        tracker.direction_changes[node_name] = 0
        tracker.last_direction[node_name] = None
        tracker.wiggle_start_time[node_name] = current_time
    
    positions = tracker.positions[node_name]
    
    # Add current position
    positions.append((current_time, Vector(current_pos)))
    
    # Keep only recent positions within time window
    time_window = settings.time_window
    positions[:] = [(t, p) for t, p in positions if current_time - t < time_window]
    
    # Need at least 3 positions to detect direction change
    if len(positions) < 3:
        return False
    
    # Calculate movement directions between consecutive positions
    directions = []
    for i in range(1, len(positions)):
        delta = positions[i][1] - positions[i-1][1]
        if delta.length > settings.min_movement:
            directions.append(delta.normalized())
    
    if len(directions) < 2:
        return False
    
    # Count direction reversals (dot product negative means opposite direction)
    direction_changes = 0
    for i in range(1, len(directions)):
        dot = directions[i].dot(directions[i-1])
        if dot < -0.3:  # Roughly opposite direction (more than 107 degrees)
            direction_changes += 1
    
    # Calculate total distance moved
    total_distance = sum(
        (positions[i][1] - positions[i-1][1]).length 
        for i in range(1, len(positions))
    )
    
    # Calculate displacement (start to end)
    displacement = (positions[-1][1] - positions[0][1]).length
    
    # Wiggle ratio: high movement but low displacement means wiggling
    wiggle_ratio = total_distance / max(displacement, 0.1)
    
    # Detect wiggle: enough direction changes and high wiggle ratio
    is_wiggling = (
        direction_changes >= settings.direction_changes_threshold and
        wiggle_ratio > settings.wiggle_ratio_threshold and
        total_distance > settings.min_total_distance
    )
    
    return is_wiggling


def clear_node_tracking(node_name):
    """Clear tracking data for a node after disconnect."""
    if node_name in tracker.positions:
        del tracker.positions[node_name]
    if node_name in tracker.direction_changes:
        del tracker.direction_changes[node_name]
    if node_name in tracker.last_direction:
        del tracker.last_direction[node_name]
    if node_name in tracker.wiggle_start_time:
        del tracker.wiggle_start_time[node_name]


class WIGGLE_OT_monitor(bpy.types.Operator):
    """Monitor node movements and disconnect on wiggle"""
    bl_idname = "node.wiggle_monitor"
    bl_label = "Wiggle Monitor"
    bl_options = {'INTERNAL'}
    
    _timer = None
    _last_positions = {}
    
    def modal(self, context, event):
        settings = context.scene.wiggle_settings
        
        if not settings.enabled:
            self.cancel(context)
            return {'CANCELLED'}
        
        if event.type == 'TIMER':
            node_tree = get_node_tree(context)
            if node_tree:
                self.check_nodes(context, node_tree, settings)
        
        return {'PASS_THROUGH'}
    
    def check_nodes(self, context, node_tree, settings):
        """Check all selected nodes for wiggling."""
        for node in node_tree.nodes:
            if node.select:
                node_key = f"{id(node_tree)}_{node.name}"
                current_pos = (node.location.x, node.location.y)
                
                # Check if position changed
                last_pos = self._last_positions.get(node_key)
                if last_pos != current_pos:
                    self._last_positions[node_key] = current_pos
                    
                    # Check for wiggle
                    if detect_wiggle(node_key, current_pos, settings):
                        # Disconnect the node!
                        num_removed = disconnect_node(node_tree, node)
                        if num_removed > 0:
                            self.report({'INFO'}, f"Disconnected '{node.name}' ({num_removed} links)")
                            clear_node_tracking(node_key)
    
    def execute(self, context):
        if context.area.type != 'NODE_EDITOR':
            self.report({'WARNING'}, "Must be in Node Editor")
            return {'CANCELLED'}
        
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.02, window=context.window)  # 50 FPS check
        wm.modal_handler_add(self)
        tracker.reset()
        self._last_positions = {}
        return {'RUNNING_MODAL'}
    
    def cancel(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        tracker.reset()
        self._last_positions = {}


class WIGGLE_OT_toggle(bpy.types.Operator):
    """Toggle wiggle detection on/off"""
    bl_idname = "node.wiggle_toggle"
    bl_label = "Toggle Wiggle Detection"
    bl_description = "Enable/disable node wiggle detection"
    
    def execute(self, context):
        settings = context.scene.wiggle_settings
        settings.enabled = not settings.enabled
        
        if settings.enabled:
            bpy.ops.node.wiggle_monitor('INVOKE_DEFAULT')
            self.report({'INFO'}, "Wiggle detection enabled")
        else:
            self.report({'INFO'}, "Wiggle detection disabled")
        
        return {'FINISHED'}


class WIGGLE_OT_disconnect_selected(bpy.types.Operator):
    """Manually disconnect all selected nodes"""
    bl_idname = "node.wiggle_disconnect_selected"
    bl_label = "Disconnect Selected Nodes"
    bl_description = "Disconnect all links from selected nodes"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        node_tree = get_node_tree(context)
        if not node_tree:
            self.report({'WARNING'}, "No active node tree")
            return {'CANCELLED'}
        
        total_removed = 0
        for node in node_tree.nodes:
            if node.select:
                total_removed += disconnect_node(node_tree, node)
        
        if total_removed > 0:
            self.report({'INFO'}, f"Removed {total_removed} links")
        else:
            self.report({'INFO'}, "No links to remove")
        
        return {'FINISHED'}


class WiggleSettings(bpy.types.PropertyGroup):
    enabled: bpy.props.BoolProperty(
        name="Enabled",
        description="Enable wiggle detection",
        default=False
    )
    
    sensitivity: bpy.props.EnumProperty(
        name="Sensitivity",
        description="How sensitive the wiggle detection is",
        items=[
            ('LOW', "Low", "Requires very aggressive wiggling"),
            ('MEDIUM', "Medium", "Balanced sensitivity"),
            ('HIGH', "High", "Detects gentle wiggling"),
        ],
        default='MEDIUM',
        update=lambda self, ctx: self.update_thresholds()
    )
    
    time_window: bpy.props.FloatProperty(
        name="Time Window",
        description="Time window to analyze movement (seconds)",
        default=0.5,
        min=0.1,
        max=2.0
    )
    
    direction_changes_threshold: bpy.props.IntProperty(
        name="Direction Changes",
        description="Minimum direction reversals to trigger disconnect",
        default=3,
        min=1,
        max=10
    )
    
    wiggle_ratio_threshold: bpy.props.FloatProperty(
        name="Wiggle Ratio",
        description="Ratio of total movement to displacement (higher = more wiggly required)",
        default=3.0,
        min=1.5,
        max=10.0
    )
    
    min_movement: bpy.props.FloatProperty(
        name="Min Movement",
        description="Minimum movement to register (pixels)",
        default=5.0,
        min=1.0,
        max=50.0
    )
    
    min_total_distance: bpy.props.FloatProperty(
        name="Min Total Distance",
        description="Minimum total distance traveled to trigger",
        default=100.0,
        min=20.0,
        max=500.0
    )
    
    def update_thresholds(self):
        """Update thresholds based on sensitivity preset."""
        if self.sensitivity == 'LOW':
            self.direction_changes_threshold = 5
            self.wiggle_ratio_threshold = 4.0
            self.min_total_distance = 150.0
        elif self.sensitivity == 'MEDIUM':
            self.direction_changes_threshold = 3
            self.wiggle_ratio_threshold = 3.0
            self.min_total_distance = 100.0
        elif self.sensitivity == 'HIGH':
            self.direction_changes_threshold = 2
            self.wiggle_ratio_threshold = 2.0
            self.min_total_distance = 50.0


class WIGGLE_PT_panel(bpy.types.Panel):
    """Wiggle That Node panel in the Node Editor sidebar"""
    bl_label = "Wiggle That Node"
    bl_idname = "WIGGLE_PT_panel"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Wiggle"
    
    def draw(self, context):
        layout = self.layout
        settings = context.scene.wiggle_settings
        
        # Main toggle
        row = layout.row()
        row.scale_y = 1.5
        if settings.enabled:
            row.operator("node.wiggle_toggle", text="Wiggle Detection ON", icon='PAUSE', depress=True)
        else:
            row.operator("node.wiggle_toggle", text="Wiggle Detection OFF", icon='PLAY')
        
        layout.separator()
        
        # Sensitivity preset
        layout.prop(settings, "sensitivity")
        
        # Advanced settings
        box = layout.box()
        box.label(text="Advanced Settings", icon='PREFERENCES')
        
        col = box.column(align=True)
        col.prop(settings, "time_window")
        col.prop(settings, "direction_changes_threshold")
        col.prop(settings, "wiggle_ratio_threshold")
        col.prop(settings, "min_movement")
        col.prop(settings, "min_total_distance")
        
        layout.separator()
        
        # Manual disconnect button
        layout.operator("node.wiggle_disconnect_selected", icon='UNLINKED')


class WIGGLE_PT_header_button(bpy.types.Header):
    """Add a button to the Node Editor header"""
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'HEADER'
    
    def draw(self, context):
        if context.area.type != 'NODE_EDITOR':
            return
        
        layout = self.layout
        settings = context.scene.wiggle_settings
        
        row = layout.row(align=True)
        icon = 'CHECKBOX_HLT' if settings.enabled else 'CHECKBOX_DEHLT'
        row.operator("node.wiggle_toggle", text="", icon=icon)


# Registration
classes = [
    WiggleSettings,
    WIGGLE_OT_monitor,
    WIGGLE_OT_toggle,
    WIGGLE_OT_disconnect_selected,
    WIGGLE_PT_panel,
    WIGGLE_PT_header_button,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.wiggle_settings = bpy.props.PointerProperty(type=WiggleSettings)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    del bpy.types.Scene.wiggle_settings


if __name__ == "__main__":
    register()
