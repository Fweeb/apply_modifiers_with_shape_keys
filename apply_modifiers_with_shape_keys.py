bl_info = {
    "name": "Apply modifier with shape keys",
    "author": "Wayne Dixon",
    "blender": (4, 3, 2),
    "version": (0, 0, 1),
    "location": "Shape Key Specials Menu",
    "description": "Apply modifiers on mesh with shape keys (Avoids the error 'Modifier cannot be applied to a mesh with shape keys').",
    "category": "Object"
}

import bpy

# Helper functions
def disable_armature_modifiers(context, selected_modifiers, disable_armatures):
    disabled_armature_modifiers = []
    if disable_armatures:
        for modifier in context.object.modifiers:
            if modifier.type == 'ARMATURE' and modifier.show_viewport:
                if modifier.name not in selected_modifiers:
                    disabled_armature_modifiers.append(modifier)
                    modifier.show_viewport = False
    return disabled_armature_modifiers

def duplicate_object(context, obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.duplicate_move(OBJECT_OT_duplicate={"linked": False, "mode": 'TRANSLATION'}, TRANSFORM_OT_translate={"value": (0, 0, 0)})
    return context.view_layer.objects.active

def apply_modifier_to_object(selected_modifiers, context):
    for modifier_name in selected_modifiers:
        bpy.ops.object.modifier_apply(modifier=modifier_name)

def save_shape_key_properties(obj, properties):
    properties_list = []
    for key_block in obj.data.shape_keys.key_blocks:
        if key_block.name == "Basis":
            continue
        properties_object = {p: getattr(key_block, p) for p in properties}
        properties_list.append(properties_object)
    return properties_list

def restore_shape_key_properties(obj, properties_list):
    for idx, key_block in enumerate(obj.data.shape_keys.key_blocks):
        if key_block.name == "Basis":
            continue
        for prop, value in properties_list[idx].items():
            setattr(key_block, prop, value)

def apply_modifiers_for_shape_keys(context, selected_modifiers, disable_armatures):
    obj = context.object
    shapes_count = len(obj.data.shape_keys.key_blocks) if obj.data.shape_keys else 0
    if shapes_count == 0:
        apply_modifier_to_object(selected_modifiers, context)
        return True, None

    # Disable armatures if necessary
    disabled_armature_modifiers = disable_armature_modifiers(context, selected_modifiers, disable_armatures)

    # Duplicate the object
    copy_obj = duplicate_object(context, obj)

    # Save the shape key properties
    properties = ["interpolation",
                "mute",
                "name",
                "relative_key",
                "slider_max",
                "slider_min",
                "value",
                "vertex_group"]
    shape_key_properties = save_shape_key_properties(obj, properties)

    # Apply modifiers to the base shape key
    bpy.ops.object.shape_key_remove(all=True)
    apply_modifier_to_object(selected_modifiers, context)

    # Apply for all shape keys
    for i, shape_properties in enumerate(shape_key_properties):
        copy_obj.select_set(True)
        bpy.context.view_layer.objects.active = copy_obj
        copy_obj.active_shape_key_index = i
        bpy.ops.object.shape_key_transfer()
        bpy.ops.object.shape_key_remove()
        bpy.ops.object.shape_key_remove(all=True)

        apply_modifier_to_object(selected_modifiers, context)
        
        # Verify vertices
        if len(obj.data.vertices) != len(copy_obj.data.vertices):
            error_message = "Shape keys ended up with different number of vertices! Apply modifiers on the correct object."
            return False, error_message
        
        # Merge shape keys
        bpy.ops.object.join_shapes()
        restore_shape_key_properties(obj, shape_key_properties)

    # Clean up the duplicate object
    bpy.data.objects.remove(copy_obj)

    # Re-enable armature modifiers
    if disable_armatures:
        for modifier in disabled_armature_modifiers:
            modifier.show_viewport = True

    return True, None

# Operator for applying modifiers
class OBJECT_OT_apply_modifiers_with_shape_keys(bpy.types.Operator):
    bl_idname = "object.apply_modifiers_with_shape_keys"
    bl_label = "Apply modifier(s) for mesh with shape keys"

    disable_armatures: bpy.props.BoolProperty(name="Don't include armature deformations", default=True)
    my_collection: bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)

    def execute(self, context):
        selected_modifiers = [o.name for o in self.my_collection if o.checked]
        if not selected_modifiers:
            self.report({'ERROR'}, 'No modifier selected!')
            return {'FINISHED'}

        success, error_info = apply_modifiers_for_shape_keys(context, selected_modifiers, self.disable_armatures)
        if not success:
            self.report({'ERROR'}, error_info)

        return {'FINISHED'}

    def draw(self, context):
        self.layout.prop(self, "disable_armatures")
        for prop in self.my_collection:
            self.layout.prop(prop, "checked", text=prop.name)

    def invoke(self, context, event):
        self.my_collection.clear()
        for modifier in context.object.modifiers:
            item = self.my_collection.add()
            item.name = modifier.name
            item.checked = False
        return context.window_manager.invoke_props_dialog(self)

# Panel for the operator
class OBJECT_PT_apply_modifiers_with_shape_keys(bpy.types.Panel):
    bl_idname = "OBJECT_PT_apply_modifiers_with_shape_keys"
    bl_label = "Multi Shape Keys"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"

    def draw(self, context):
        self.layout.operator("object.apply_modifier_for_object_with_shape_keys")

# Register and unregister classes
def menu_func(self, context):
    self.layout.operator(ApplyModifierForObjectWithShapeKeysOperator.bl_idname)
    
classes = [
    OBJECT_OT_apply_modifiers_with_shape_keys,
    OBJECT_PT_apply_modifiers_with_shape_keys,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_MT_object.append(menu_func)
 
def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    bpy.types.VIEW3D_MT_object.append(menu_func)


if __name__ == "__main__":
    register()
