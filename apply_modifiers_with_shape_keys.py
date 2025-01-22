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


# ###
# Issues to solve:
# - doesn't work 
# - if a modifier is broken it will throw and error rather than just saying "skipping"
# - if a modifier is disabled it should enable it before running the operation
# - check if a modifier is disabled, enable it before applying
# - add support to copy and paste the drivers and animation data (on shape keys)

# Helper functions
def disable_armature_modifiers(context, selected_modifiers, disable_armatures):
    ''' if there is an armature modifier on the mesh, you can disable it so it doesn't affect the deformation
    it will be reset back after the add-on is finished '''
    disabled_armature_modifiers = []
    if disable_armatures:
        for modifier in context.object.modifiers:
            if modifier.type == 'ARMATURE' and modifier.show_viewport:
                if modifier.name not in selected_modifiers:
                    disabled_armature_modifiers.append(modifier)
                    modifier.show_viewport = False
    return disabled_armature_modifiers

def duplicate_object(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.duplicate_move(OBJECT_OT_duplicate={"linked": False, "mode": 'TRANSLATION'}, TRANSFORM_OT_translate={"value": (0, 0, 0)})

def apply_modifier_to_object(context, obj, selected_modifiers):
    context.view_layer.objects.active = obj
    for modifier_name in selected_modifiers:
        bpy.ops.object.modifier_apply(modifier=modifier_name)

def apply_shape_keys(ob):
    basis_key = ob.data.shape_keys.key_blocks[0]
    # Create a temporary shape key that's a mix of current keys
    temp_shape_key = ob.shape_key_add(name="TEMP KEY", from_mix=True) #XXX Assumes there's already shape keys on the object

    # Copy the coordinates of the temporary shape key to the Basis
    for i in range(0, len(basis_key.points)):
        #print(i, temp_shape_key.points[i].co) #DEBUG
        basis_key.points[i].co = temp_shape_key.points[i].co

    # Remove all shape keys
    for shape_key in active_object.data.shape_keys.key_blocks:
        ob.shape_key_remove(shape_key)

def save_shape_key_properties(obj, properties):
    ''' This function will save the settings on the shape keys (min/max etc) '''
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

def apply_modifiers_with_shape_keys(context, selected_modifiers, disable_armatures):
    ''' Apply the selected modifiers to the mesh even if it has shape keys '''
    original_obj = context.view_layer.objects.active
    shapes_count = len(original_obj.data.shape_keys.key_blocks) if original_obj.data.shape_keys else 0
    if shapes_count == 0: # if there are no shape keys just apply the selected modifiers
        apply_modifier_to_object(context, original_obj, selected_modifiers)
        return True, None

    # Disable armatures if necessary
    disabled_armature_modifiers = disable_armature_modifiers(context, selected_modifiers, disable_armatures)

    # Duplicate the object
    duplicate_object(original_obj)
    copy_obj = context.view_layer.objects.active

    # Make the Original Object the active object
    context.view_layer.objects.active = original_obj
    
    # Save the shape key properties
    properties = ["name", "mute", "lock_shape", "value", "slider_min", "slider_max", "vertex_group", "relative_key"]
    shape_key_properties = save_shape_key_properties(original_obj, properties)

    # Remove all shape keys and apply modifiers on the original
    bpy.ops.object.shape_key_remove(all=True)
    apply_modifier_to_object(context, original_obj, selected_modifiers)

    # Add a basis shape key back to the original object
    original_obj.shape_key_add(name='Basis',from_mix=False)

    # Loop over the original shape keys, create a temp mesh, apply single shape, apply modifers and merge back to the original (1 shape at a time)
    for i, shape_properties in enumerate(shape_key_properties):
        # Create a temp object
        context.view_layer.objects.active = copy_obj
        duplicate_object(copy_obj)
        temp_obj = bpy.context.active_object

        # Pin the shape we want
        bpy.data.objects[temp_obj.name].show_only_shape_key = True
        temp_obj.active_shape_key_index = i + 1

        # Apply the shape key to freeze the mesh in that position
        apply_shape_keys(temp_obj)

        # Apply modifiers to temp object (THIS ISN'T WORKING HERE BUT IT WORKS EARLIER)
        apply_modifier_to_object(context, temp_obj, selected_modifiers)

        # Verify the meshes have the same amount of verts
        # if len(original_obj.data.vertices) != len(temp_obj.data.vertices):
        #     error_message = "Objects have a different number of vertices!"
        #     return False, error_message

        # Add a basis shape key back to the temp object
        original_obj.shape_key_add(name='Basis',from_mix=False)

        # Transfer the temp object as a shape back to orginal
        temp_obj.select_set(True)
        context.view_layer.objects.active = original_obj
        bpy.ops.object.shape_key_transfer()

        # Restore shape key properties (THIS DOESN'T WORK)
        # restore_shape_key_properties(original_obj, shape_key_properties)

        # Clean up the temp object
        #bpy.data.objects.remove(temp_obj)

    # Clean up the duplicate object
    #bpy.data.objects.remove(copy_obj)

    # Re-enable armature modifiers
    if disable_armatures:
        for modifier in disabled_armature_modifiers:
            modifier.show_viewport = True

    return True, None

# Property Collection
class ModifierList(bpy.types.PropertyGroup): 
    apply_modifier: bpy.props.BoolProperty(name="", default=False)


# Operator for applying modifiers
class OBJECT_OT_apply_modifiers_with_shape_keys(bpy.types.Operator):
    ''' Apply selected modifiers to mesh even if it has shape keys '''
    bl_idname = "object.apply_modifiers_with_shape_keys"
    bl_label = "Apply modifier(s) for mesh with shape keys"

    disable_armatures: bpy.props.BoolProperty(name="Exclude armature deformation", default=True)
    collection_property: bpy.props.CollectionProperty(type=ModifierList)

    def execute(self, context):
        selected_modifiers = [o.name for o in self.collection_property if o.apply_modifier]
        if not selected_modifiers:
            self.report({'ERROR'}, 'No modifiers selected!')
            return {'FINISHED'}

        success, error_info = apply_modifiers_with_shape_keys(context, selected_modifiers, self.disable_armatures)
        if not success:
            self.report({'ERROR'}, error_info)

        return {'FINISHED'}

    def draw(self, context):
        self.layout.label(text="Select which modifier(s) to apply")
        box = self.layout.box()
        for prop in self.collection_property:
            box.prop(prop, "apply_modifier", text=prop.name)

        self.layout.separator() #TODO: only show this if there are any armarture modifiers in the stack
        self.layout.prop(self, "disable_armatures")

    def invoke(self, context, event):
        self.collection_property.clear()
        for modifier in context.object.modifiers:
            item = self.collection_property.add()
            item.name = modifier.name
            item.apply_modifier = False
        return context.window_manager.invoke_props_dialog(self)

# Register and unregister classes
def menu_func(self, context):
    self.layout.separator()  # Add a separator before the operator cleaner look
    self.layout.operator(OBJECT_OT_apply_modifiers_with_shape_keys.bl_idname)
    
classes = [
    ModifierList,
    OBJECT_OT_apply_modifiers_with_shape_keys,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.MESH_MT_shape_key_context_menu.append(menu_func)
 
def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    bpy.types.MESH_MT_shape_key_context_menu.append(menu_func)


if __name__ == "__main__":
    register()
