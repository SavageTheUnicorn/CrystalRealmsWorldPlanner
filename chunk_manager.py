import pygame
import math
from constants import Layer


class SpriteCache:
    """Cache for scaled sprites to avoid repeated scaling operations"""
    
    def __init__(self, max_cache_size=1000):
        self.cache = {}
        self.access_order = []
        self.max_size = max_cache_size
    
    def get_scaled_sprite(self, sprite_id, sprite, target_size):
        """Get a cached scaled sprite or create and cache it"""
        cache_key = (sprite_id, target_size)
        
        if cache_key in self.cache:
            # Move to end of access order (most recently used)
            self.access_order.remove(cache_key)
            self.access_order.append(cache_key)
            return self.cache[cache_key]
        
        # Create scaled sprite
        if target_size == (sprite.get_width(), sprite.get_height()):
            # No scaling needed
            scaled_sprite = sprite
        else:
            try:
                # Use smoothscale for better quality when scaling up, regular scale when scaling down
                if target_size[0] > sprite.get_width() or target_size[1] > sprite.get_height():
                    scaled_sprite = pygame.transform.smoothscale(sprite, target_size)
                else:
                    scaled_sprite = pygame.transform.scale(sprite, target_size)
                
                # Convert to display format for faster blitting
                if sprite.get_flags() & pygame.SRCALPHA:
                    scaled_sprite = scaled_sprite.convert_alpha()
                else:
                    scaled_sprite = scaled_sprite.convert()
            except Exception:
                scaled_sprite = pygame.transform.scale(sprite, target_size)
                scaled_sprite = scaled_sprite.convert_alpha()
        
        # Cache the result
        self.cache[cache_key] = scaled_sprite
        self.access_order.append(cache_key)
        
        # Limit cache size
        while len(self.cache) > self.max_size:
            oldest_key = self.access_order.pop(0)
            del self.cache[oldest_key]
        
        return scaled_sprite
    
    def clear(self):
        """Clear the sprite cache"""
        self.cache.clear()
        self.access_order.clear()


class OptimizedChunk:
    """Optimized chunk with better caching and rendering"""
    
    def __init__(self, x, y, size):
        self.x = x  # Chunk grid position X
        self.y = y  # Chunk grid position Y
        self.size = size  # Chunk size in tiles
        self.dirty = True  # Whether the chunk needs re-rendering
        self.surface = None  # Pre-rendered surface
        self.border = 20  # Border size for seamless rendering
        
        # Performance optimizations
        self.last_zoom = None
        self.last_tile_size = None
        self.blocks_hash = None  # Hash of blocks for change detection
        self.visible_bounds = None  # Cached visible tile bounds
        
        # Layer surfaces for optimized compositing
        self.layer_surfaces = {}
        self.layer_dirty = {Layer.BACKGROUND: True, Layer.MIDGROUND: True}
    
    def needs_rerender(self, world_planner, base_tile_size):
        """Check if chunk needs re-rendering based on changes"""
        current_zoom = world_planner.tile_size * world_planner.zoom
        
        # Force rerender if explicitly marked dirty
        if self.dirty:
            return True
        
        # Check if zoom or tile size changed
        if (self.last_zoom != current_zoom or 
            self.last_tile_size != base_tile_size):
            return True
        
        # Check if blocks changed by computing hash (only if not dirty)
        current_hash = self.compute_blocks_hash(world_planner)
        if self.blocks_hash != current_hash:
            return True
        
        return False
    
    def compute_blocks_hash(self, world_planner):
        """Compute hash of blocks in this chunk for change detection"""
        hash_data = []
        
        # Include blocks with border for seamless rendering
        start_x = self.x * self.size - self.border
        start_y = self.y * self.size - self.border
        end_x = (self.x + 1) * self.size + self.border
        end_y = (self.y + 1) * self.size + self.border
        
        for layer_enum in [Layer.BACKGROUND, Layer.MIDGROUND]:
            layer = world_planner.layers[layer_enum]
            for x in range(start_x, end_x):
                for y in range(start_y, end_y):
                    if (x, y) in layer:
                        block_data = layer[(x, y)]
                        hash_data.append((x, y, layer_enum.value, block_data.get('id', ''), block_data.get('state', 0)))
        
        return hash(tuple(hash_data))
    
    def render_layer(self, world_planner, layer_enum, base_tile_size, surface):
        """Render a specific layer to the surface"""
        layer = world_planner.layers[layer_enum]
        world_width = world_planner.world_width
        world_height = world_planner.world_height
        
        # Calculate chunk bounds with border
        start_tile_x = self.x * self.size - self.border
        start_tile_y = self.y * self.size - self.border
        end_tile_x = (self.x + 1) * self.size + self.border
        end_tile_y = (self.y + 1) * self.size + self.border
        
        # Collect and sort blocks for this layer
        layer_blocks = []
        for x in range(start_tile_x, end_tile_x):
            for y in range(start_tile_y, end_tile_y):
                if (0 <= x < world_width and 0 <= y < world_height and 
                    (x, y) in layer):
                    layer_blocks.append(((x, y), layer[(x, y)]))
        
        # Sort blocks for proper rendering order
        sorted_blocks = sorted(layer_blocks, key=lambda item: (
            0 if item[1].get('isBackground', False) else 1,
            0 if item[1].get('isBedrock', False) else 1,
            -item[0][1]  # Reverse Y for proper sprite layering
        ))
        
        # Render blocks
        for (x, y), block_data in sorted_blocks:
            local_x = (x - start_tile_x) * base_tile_size
            local_y = (y - start_tile_y) * base_tile_size
            
            # Use optimized tile renderer
            world_planner.tile_renderer.draw_block_optimized(
                surface, world_planner, x, y, block_data,
                local_x, local_y, base_tile_size, layer_enum
            )
    
    def render(self, world_planner, base_tile_size, sprite_cache):
        """Render this chunk to a surface with optimizations - FIXED GRID AND BORDERS"""
        # Always update state first, then check if we need to re-render
        current_zoom = world_planner.tile_size * world_planner.zoom
        current_hash = self.compute_blocks_hash(world_planner)
        
        # Check if we need to re-render
        if (not self.dirty and 
            self.last_zoom == current_zoom and 
            self.last_tile_size == base_tile_size and
            self.blocks_hash == current_hash and
            self.surface is not None):
            return
        
        # Calculate surface size (includes border for seamless sprite rendering)
        expanded_size = self.size + 2 * self.border
        chunk_pixel_size = expanded_size * base_tile_size
        
        # Create optimized surface
        if self.surface is None or self.surface.get_size() != (chunk_pixel_size, chunk_pixel_size):
            self.surface = pygame.Surface((chunk_pixel_size, chunk_pixel_size), pygame.SRCALPHA)
            self.surface = self.surface.convert_alpha()
        
        # Clear surface efficiently
        self.surface.fill((0, 0, 0, 0))
        
        # Check for world background
        has_world_background = world_planner.background_manager.get_current_background() is not None
        
        if not has_world_background:
            self.surface.fill((17, 17, 17))
        
        # FIXED: Draw grid ONLY in main area (will be drawn by main area extraction)
        if world_planner.show_grid:
            self.draw_grid_in_main_area_only(world_planner, base_tile_size, has_world_background)
        
        # Render sprites with full border area for seamless rendering
        for layer_enum in [Layer.BACKGROUND, Layer.MIDGROUND]:
            self.render_layer(world_planner, layer_enum, base_tile_size, self.surface)
        
        # Update state AFTER successful render
        self.dirty = False
        self.last_zoom = current_zoom
        self.last_tile_size = base_tile_size
        self.blocks_hash = current_hash
    
    def force_visual_update(self, world_planner, base_tile_size):
        """FIXED: Force immediate visual update with proper state management"""
        # Clear cached state to ensure re-render
        self.dirty = True
        self.blocks_hash = None
        
        # Render immediately - this will update all state correctly
        self.render(world_planner, base_tile_size, None)
        
        # No need to restore old state - let render() handle everything properly
    
    def draw_chunk_grid_optimized(self, world_planner, base_tile_size, expanded_size, has_world_background):
        """Fixed grid drawing that only draws in chunk's main area, not border area"""
        if has_world_background:
            grid_color = (70, 70, 70)
        else:
            grid_color = (70, 70, 70)
        
        # Calculate the chunk's MAIN area (excluding border)
        main_start_tile_x = self.x * self.size
        main_start_tile_y = self.y * self.size
        main_end_tile_x = (self.x + 1) * self.size
        main_end_tile_y = (self.y + 1) * self.size
        
        # World boundaries
        world_width = world_planner.world_width
        world_height = world_planner.world_height
        
        # Clamp to world boundaries
        main_start_tile_x = max(0, main_start_tile_x)
        main_start_tile_y = max(0, main_start_tile_y)
        main_end_tile_x = min(world_width, main_end_tile_x)
        main_end_tile_y = min(world_height, main_end_tile_y)
        
        # Convert world tile coordinates to local chunk surface coordinates
        chunk_start_tile_x = self.x * self.size - self.border
        chunk_start_tile_y = self.y * self.size - self.border
        
        # Draw vertical lines ONLY for the main area
        for world_tile_x in range(main_start_tile_x, main_end_tile_x + 1):
            if 0 <= world_tile_x < world_width:
                # Convert to local surface coordinates
                local_x = (world_tile_x - chunk_start_tile_x) * base_tile_size
                
                # Y range for this vertical line (only in main area)
                y_start = (main_start_tile_y - chunk_start_tile_y) * base_tile_size
                y_end = (main_end_tile_y - chunk_start_tile_y) * base_tile_size
                
                # Clamp to surface bounds
                y_start = max(0, y_start)
                y_end = min(expanded_size * base_tile_size, y_end)
                
                if y_end > y_start:
                    pygame.draw.line(self.surface, grid_color, (local_x, y_start), (local_x, y_end), 1)
        
        # Draw horizontal lines ONLY for the main area
        for world_tile_y in range(main_start_tile_y, main_end_tile_y + 1):
            if 0 <= world_tile_y < world_height:
                # Convert to local surface coordinates
                local_y = (world_tile_y - chunk_start_tile_y) * base_tile_size
                
                # X range for this horizontal line (only in main area)
                x_start = (main_start_tile_x - chunk_start_tile_x) * base_tile_size
                x_end = (main_end_tile_x - chunk_start_tile_x) * base_tile_size
                
                # Clamp to surface bounds
                x_start = max(0, x_start)
                x_end = min(expanded_size * base_tile_size, x_end)
                
                if x_end > x_start:
                    pygame.draw.line(self.surface, grid_color, (x_start, local_y), (x_end, local_y), 1)
                    
    def draw_grid_in_main_area_only(self, world_planner, base_tile_size, has_world_background):
        """Draw grid only in the main chunk area AND within world boundaries"""
        if has_world_background:
            grid_color = (70, 70, 70)
        else:
            grid_color = (70, 70, 70)
        
        # Calculate main area bounds in surface coordinates
        border_pixels = self.border * base_tile_size
        main_area_size = self.size * base_tile_size
        
        # Calculate world tile coordinates for this chunk
        chunk_start_tile_x = self.x * self.size
        chunk_start_tile_y = self.y * self.size
        chunk_end_tile_x = chunk_start_tile_x + self.size
        chunk_end_tile_y = chunk_start_tile_y + self.size
        
        # Clamp to world boundaries
        world_width = world_planner.world_width
        world_height = world_planner.world_height
        
        # Calculate the actual range of tiles we should draw grid for
        actual_start_tile_x = max(0, chunk_start_tile_x)
        actual_start_tile_y = max(0, chunk_start_tile_y)
        actual_end_tile_x = min(world_width, chunk_end_tile_x)
        actual_end_tile_y = min(world_height, chunk_end_tile_y)
        
        # Convert back to local surface coordinates
        # Vertical lines - only draw where tiles actually exist in the world
        for world_tile_x in range(actual_start_tile_x, actual_end_tile_x + 1):
            # Convert world tile coordinate to local surface coordinate
            local_tile_x = world_tile_x - chunk_start_tile_x
            x_pos = border_pixels + local_tile_x * base_tile_size
            
            # Calculate Y range for this vertical line (only within world bounds)
            y_start = border_pixels + max(0, actual_start_tile_y - chunk_start_tile_y) * base_tile_size
            y_end = border_pixels + min(self.size, actual_end_tile_y - chunk_start_tile_y) * base_tile_size
            
            if y_end > y_start:
                pygame.draw.line(self.surface, grid_color, (x_pos, y_start), (x_pos, y_end), 1)
        
        # Horizontal lines - only draw where tiles actually exist in the world
        for world_tile_y in range(actual_start_tile_y, actual_end_tile_y + 1):
            # Convert world tile coordinate to local surface coordinate
            local_tile_y = world_tile_y - chunk_start_tile_y
            y_pos = border_pixels + local_tile_y * base_tile_size
            
            # Calculate X range for this horizontal line (only within world bounds)
            x_start = border_pixels + max(0, actual_start_tile_x - chunk_start_tile_x) * base_tile_size
            x_end = border_pixels + min(self.size, actual_end_tile_x - chunk_start_tile_x) * base_tile_size
            
            if x_end > x_start:
                pygame.draw.line(self.surface, grid_color, (x_start, y_pos), (x_end, y_pos), 1)


class OptimizedChunkManager:
    """Optimized chunk manager with better performance"""
    
    def __init__(self, world_planner, chunk_size=16):
        self.world_planner = world_planner
        self.chunk_size = chunk_size
        self.chunks = {}
        self.cached_zoom = None
        self.max_chunks_per_frame = 3  # Reduced for better frame rate
        
        # Performance optimizations
        self.sprite_cache = SpriteCache(max_cache_size=2000)
        self.visible_chunks_cache = None
        self.last_camera_pos = None
        self.last_viewport_size = None
        
        # Frustum culling bounds
        self.viewport_bounds = None
        
        # Background surface cache
        self.background_surface_cache = {}
        self.last_background_id = None
    
    def get_chunk_key(self, tile_x, tile_y):
        """Convert tile coordinates to chunk key"""
        chunk_x = tile_x // self.chunk_size
        chunk_y = tile_y // self.chunk_size
        return (chunk_x, chunk_y)
    
    def get_or_create_chunk(self, chunk_x, chunk_y):
        """Get an existing chunk or create a new one"""
        key = (chunk_x, chunk_y)
        if key not in self.chunks:
            self.chunks[key] = OptimizedChunk(chunk_x, chunk_y, self.chunk_size)
        return self.chunks[key]
    
    def invalidate_chunk(self, tile_x, tile_y):
        """Mark a chunk as needing re-rendering"""
        key = self.get_chunk_key(tile_x, tile_y)
        
        if key in self.chunks:
            self.chunks[key].dirty = True
        else:
            chunk_x, chunk_y = key
            self.chunks[key] = OptimizedChunk(chunk_x, chunk_y, self.chunk_size)
            self.chunks[key].dirty = True
        
        # Invalidate neighboring chunks for sprites that might extend across boundaries
        chunk_x, chunk_y = key
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                
                neighbor_key = (chunk_x + dx, chunk_y + dy)
                if neighbor_key in self.chunks:
                    self.chunks[neighbor_key].dirty = True
    
    def invalidate_all_chunks(self):
        """Mark all chunks as dirty and clear caches with force"""
        for chunk in self.chunks.values():
            chunk.dirty = True
            chunk.blocks_hash = None
            chunk.last_zoom = None
            chunk.surface = None
        
        # Clear caches
        self.sprite_cache.clear()
        self.visible_chunks_cache = None
        self.background_surface_cache.clear()
    
    def force_render_visible_chunks(self, camera_x, camera_y, effective_tile_size):
        """Force immediate rendering of visible chunks for smooth interaction"""
        visible_chunks = self.get_visible_chunks_optimized(
            camera_x, camera_y,
            self.world_planner.canvas_rect.width,
            self.world_planner.canvas_rect.height,
            effective_tile_size
        )
        
        base_tile_size = self.world_planner.tile_size
        for key in visible_chunks[:self.max_chunks_per_frame * 2]:  # Render more chunks when forced
            if key in self.chunks:
                chunk = self.chunks[key]
                if chunk.dirty:
                    chunk.render(self.world_planner, base_tile_size, self.sprite_cache)
    
    def force_update_affected_chunks(self, affected_positions):
        """Force immediate chunk updates that work at all zoom levels"""
        if not affected_positions:
            return
        
        base_tile_size = self.world_planner.tile_size
        updated_chunks = set()
        
        # Step 1: Update all affected chunks and invalidate their cache entries
        for x, y in affected_positions:
            chunk_key = self.get_chunk_key(x, y)
            if chunk_key not in updated_chunks:
                chunk = self.get_or_create_chunk(chunk_key[0], chunk_key[1])
                
                # Force visual update
                chunk.force_visual_update(self.world_planner, base_tile_size)
                
                # CRITICAL: Invalidate all cached scaled versions of this chunk
                self.invalidate_chunk_cache_entries(chunk)
                
                updated_chunks.add(chunk_key)
                
                # Also update immediate neighbors
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        if dx == 0 and dy == 0:
                            continue
                        neighbor_key = (chunk_key[0] + dx, chunk_key[1] + dy)
                        if neighbor_key not in updated_chunks:
                            neighbor_chunk = self.get_or_create_chunk(neighbor_key[0], neighbor_key[1])
                            neighbor_chunk.force_visual_update(self.world_planner, base_tile_size)
                            self.invalidate_chunk_cache_entries(neighbor_chunk)
                            updated_chunks.add(neighbor_key)
        
        # Step 2: Mark for immediate rendering
        self.mark_chunks_for_immediate_render(affected_positions)
    
    def mark_chunks_for_immediate_render(self, affected_positions):
        """Mark chunks as requiring immediate rendering in the next frame"""
        if not hasattr(self, 'immediate_render_chunks'):
            self.immediate_render_chunks = set()
        
        for x, y in affected_positions:
            chunk_key = self.get_chunk_key(x, y)
            chunk = self.get_or_create_chunk(chunk_key[0], chunk_key[1])
            chunk.dirty = True
            chunk.blocks_hash = None  # Force content check
            self.immediate_render_chunks.add(chunk_key)
            
            # Also mark immediate neighbors
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    neighbor_key = (chunk_key[0] + dx, chunk_key[1] + dy)
                    neighbor_chunk = self.get_or_create_chunk(neighbor_key[0], neighbor_key[1])
                    neighbor_chunk.dirty = True
                    neighbor_chunk.blocks_hash = None
                    self.immediate_render_chunks.add(neighbor_key)
    
    def invalidate_chunk_cache_entries(self, chunk):
        """Invalidate all cached scaled versions of a chunk surface"""
        if chunk.surface is None:
            return
        
        chunk_surface_id = id(chunk.surface)
        
        # Remove all cache entries for this chunk surface at any scale
        keys_to_remove = []
        for cache_key in self.sprite_cache.cache.keys():
            if isinstance(cache_key, tuple) and len(cache_key) >= 2:
                if cache_key[0] == chunk_surface_id:
                    keys_to_remove.append(cache_key)
        
        for key in keys_to_remove:
            if key in self.sprite_cache.cache:
                del self.sprite_cache.cache[key]
                if key in self.sprite_cache.access_order:
                    self.sprite_cache.access_order.remove(key)
    
    def draw_chunk_at_zoom(self, surface, chunk, screen_x, screen_y, chunk_pixel_size, 
                        expanded_size, base_tile_size, effective_tile_size):
        """Draw a chunk at the current zoom level with proper scaling"""
        
        # Calculate the actual size the chunk surface should be
        expected_surface_size = expanded_size * base_tile_size
        
        if effective_tile_size == base_tile_size:
            # No scaling needed - direct blit
            surface.blit(chunk.surface, (screen_x, screen_y))
        else:
            # Need to scale the chunk surface
            cache_key = (id(chunk.surface), chunk_pixel_size)
            
            # Check if we have a cached scaled version
            if cache_key in self.sprite_cache.cache:
                scaled_surface = self.sprite_cache.cache[cache_key]
            else:
                # Create new scaled version
                try:
                    if chunk_pixel_size > expected_surface_size:
                        # Scaling up - use smoothscale for better quality
                        scaled_surface = pygame.transform.smoothscale(
                            chunk.surface, (chunk_pixel_size, chunk_pixel_size)
                        )
                    else:
                        # Scaling down - use regular scale
                        scaled_surface = pygame.transform.scale(
                            chunk.surface, (chunk_pixel_size, chunk_pixel_size)
                        )
                    
                    scaled_surface = scaled_surface.convert_alpha()
                    
                    # Cache it
                    self.sprite_cache.cache[cache_key] = scaled_surface
                    self.sprite_cache.access_order.append(cache_key)
                    
                    # Manage cache size
                    while len(self.sprite_cache.cache) > self.sprite_cache.max_size:
                        oldest_key = self.sprite_cache.access_order.pop(0)
                        if oldest_key in self.sprite_cache.cache:
                            del self.sprite_cache.cache[oldest_key]
                            
                except Exception as e:
                    print(f"Error scaling chunk surface: {e}")
                    # Fallback to original surface
                    scaled_surface = chunk.surface
            
            # Draw the scaled surface
            surface.blit(scaled_surface, (screen_x, screen_y))
    
    def draw_chunk_main_area_only(self, surface, chunk, screen_x, screen_y, chunk_pixel_size, 
                                base_tile_size, effective_tile_size):
        """Draw chunk with extended sprite preservation"""
        
        border_pixels = chunk.border * base_tile_size
        main_area_size = chunk.size * base_tile_size
        
        # Calculate the area to extract - include full border for now
        src_x = 0  # Include left border
        src_y = 0  # Include top border  
        src_width = chunk.surface.get_width()  # Full width including borders
        src_height = chunk.surface.get_height()  # Full height including borders
        
        # Calculate where to draw it on screen (accounting for borders)
        draw_x = screen_x - border_pixels
        draw_y = screen_y - border_pixels
        
        try:
            if effective_tile_size == base_tile_size:
                # No scaling needed - draw full chunk surface
                surface.blit(chunk.surface, (draw_x, draw_y))
            else:
                # Scale the full chunk surface
                cache_key = (id(chunk.surface), "full_chunk", chunk_pixel_size)
                
                if cache_key in self.sprite_cache.cache:
                    scaled_surface = self.sprite_cache.cache[cache_key]
                else:
                    # Calculate scaled size for full chunk including borders
                    expanded_size = self.chunk_size + 2 * chunk.border
                    full_scaled_size = int(expanded_size * effective_tile_size)
                    
                    scaled_surface = pygame.transform.scale(chunk.surface, (full_scaled_size, full_scaled_size))
                    scaled_surface = scaled_surface.convert_alpha()
                    
                    # Cache it
                    self.sprite_cache.cache[cache_key] = scaled_surface
                    self.sprite_cache.access_order.append(cache_key)
                    
                    # Manage cache size
                    while len(self.sprite_cache.cache) > self.sprite_cache.max_size:
                        oldest_key = self.sprite_cache.access_order.pop(0)
                        if oldest_key in self.sprite_cache.cache:
                            del self.sprite_cache.cache[oldest_key]
                
                # Adjust draw position for scaling
                border_scaled = int(border_pixels * effective_tile_size / base_tile_size)
                draw_x = screen_x - border_scaled
                draw_y = screen_y - border_scaled
                surface.blit(scaled_surface, (draw_x, draw_y))
                
        except Exception as e:
            print(f"Error drawing full chunk: {e}")
            # Fallback to original main area only
            src_rect = pygame.Rect(border_pixels, border_pixels, main_area_size, main_area_size)
            if (src_rect.right <= chunk.surface.get_width() and 
                src_rect.bottom <= chunk.surface.get_height()):
                main_area_surface = chunk.surface.subsurface(src_rect)
                surface.blit(main_area_surface, (screen_x, screen_y))
    
    def draw_updated_chunks_immediately(self, updated_chunk_keys):
        """NEW: Immediately draw updated chunks to screen for instant feedback"""
        if not updated_chunk_keys:
            return
            
        # Get current screen surface from world planner
        screen = self.world_planner.screen
        
        # Calculate current rendering parameters
        camera_x = int(round(self.world_planner.camera_x))
        camera_y = int(round(self.world_planner.camera_y))
        effective_tile_size = int(self.world_planner.tile_size * self.world_planner.zoom)
        
        # Screen bounds for clipping
        canvas_rect = self.world_planner.canvas_rect
        
        # Set clipping to canvas area
        original_clip = screen.get_clip()
        screen.set_clip(canvas_rect)
        
        try:
            # Draw each updated chunk immediately
            for chunk_key in updated_chunk_keys:
                if chunk_key in self.chunks:
                    chunk = self.chunks[chunk_key]
                    if chunk.surface is not None:
                        self.draw_single_chunk_to_screen(screen, chunk, camera_x, camera_y, effective_tile_size)
            
            # Force immediate screen update for just the canvas area
            pygame.display.update(canvas_rect)
            
        finally:
            # Restore original clipping
            screen.set_clip(original_clip)
    
    def draw_single_chunk_to_screen(self, surface, chunk, camera_x, camera_y, effective_tile_size):
        """NEW: Draw a single chunk to the screen"""
        # Calculate screen position
        screen_left = self.world_planner.toolbar_width + self.world_planner.resize_handle_width
        screen_x = ((chunk.x * self.chunk_size - chunk.border) * effective_tile_size - 
                   camera_x + screen_left)
        screen_y = (chunk.y * self.chunk_size - chunk.border) * effective_tile_size - camera_y
        
        # Calculate chunk size
        expanded_size = self.chunk_size + 2 * chunk.border
        chunk_pixel_size = int(expanded_size * effective_tile_size)
        
        # Frustum culling - only draw if visible
        canvas_rect = self.world_planner.canvas_rect
        if (screen_x + chunk_pixel_size < canvas_rect.left or screen_x > canvas_rect.right or
            screen_y + chunk_pixel_size < canvas_rect.top or screen_y > canvas_rect.bottom):
            return
        
        # Draw the chunk
        if effective_tile_size == self.world_planner.tile_size:
            # No scaling needed
            surface.blit(chunk.surface, (screen_x, screen_y))
        else:
            # Scale the chunk surface
            cache_key = (id(chunk.surface), chunk_pixel_size)
            scaled_surface = self.sprite_cache.get_scaled_sprite(
                cache_key, chunk.surface, (chunk_pixel_size, chunk_pixel_size)
            )
            surface.blit(scaled_surface, (screen_x, screen_y))
    
    def get_visible_chunks_optimized(self, camera_x, camera_y, width, height, effective_tile_size):
        """Optimized visible chunk calculation with caching"""
        current_viewport = (camera_x, camera_y, width, height, effective_tile_size)
        
        # Use cached result if viewport hasn't changed much
        if (self.visible_chunks_cache is not None and 
            self.last_camera_pos is not None and
            self.last_viewport_size == (width, height)):
            
            # Check if camera moved significantly
            camera_delta = (abs(camera_x - self.last_camera_pos[0]) + 
                          abs(camera_y - self.last_camera_pos[1]))
            
            if camera_delta < effective_tile_size * 2:  # Small movement threshold
                return self.visible_chunks_cache
        
        # Calculate visible chunks
        world_width_px = self.world_planner.world_width * effective_tile_size
        world_height_px = self.world_planner.world_height * effective_tile_size
        
        # Add padding for smoother scrolling
        padding = effective_tile_size * 2
        
        # Calculate tile bounds with padding
        start_tile_x = max(0, (camera_x - padding) // effective_tile_size)
        start_tile_y = max(0, (camera_y - padding) // effective_tile_size)
        end_tile_x = min(self.world_planner.world_width - 1,
                        (camera_x + width + padding) // effective_tile_size + 1)
        end_tile_y = min(self.world_planner.world_height - 1,
                        (camera_y + height + padding) // effective_tile_size + 1)
        
        # Convert to chunk coordinates
        start_chunk_x = int(start_tile_x) // self.chunk_size
        start_chunk_y = int(start_tile_y) // self.chunk_size
        end_chunk_x = int(end_tile_x) // self.chunk_size
        end_chunk_y = int(end_tile_y) // self.chunk_size
        
        # World chunk bounds
        max_chunk_x = (self.world_planner.world_width - 1) // self.chunk_size
        max_chunk_y = (self.world_planner.world_height - 1) // self.chunk_size
        
        # Generate visible chunk keys
        visible_chunks = []
        for cy in range(max(0, start_chunk_y), min(max_chunk_y + 1, end_chunk_y + 1)):
            for cx in range(max(0, start_chunk_x), min(max_chunk_x + 1, end_chunk_x + 1)):
                visible_chunks.append((cx, cy))
        
        # Cache results
        self.visible_chunks_cache = visible_chunks
        self.last_camera_pos = (camera_x, camera_y)
        self.last_viewport_size = (width, height)
        
        return visible_chunks
    
    def render_chunks_optimized(self, visible_chunks, base_tile_size):
        """Optimized chunk rendering with immediate brush update support"""
        chunks_rendered = 0
        
        # Initialize immediate render set if it doesn't exist
        if not hasattr(self, 'immediate_render_chunks'):
            self.immediate_render_chunks = set()
        
        # First, render all immediate chunks (from brush operations) with no limits
        immediate_chunks_to_render = []
        for chunk_key in list(self.immediate_render_chunks):
            if chunk_key in visible_chunks and chunk_key in self.chunks:
                chunk = self.chunks[chunk_key]
                if chunk.needs_rerender(self.world_planner, base_tile_size):
                    immediate_chunks_to_render.append(chunk)
        
        # Render immediate chunks without limits
        for chunk in immediate_chunks_to_render:
            chunk.render(self.world_planner, base_tile_size, self.sprite_cache)
            chunks_rendered += 1
        
        # Clear the immediate render set
        self.immediate_render_chunks.clear()
        
        # Then render other chunks with normal limits
        if chunks_rendered < self.max_chunks_per_frame:
            # Prioritize chunks by distance from center
            if visible_chunks:
                center_chunk_x = sum(key[0] for key in visible_chunks) / len(visible_chunks)
                center_chunk_y = sum(key[1] for key in visible_chunks) / len(visible_chunks)
                
                def chunk_distance(key):
                    cx, cy = key
                    return (cx - center_chunk_x) ** 2 + (cy - center_chunk_y) ** 2
                
                visible_chunks = sorted(visible_chunks, key=chunk_distance)
            
            # Render remaining chunks
            for key in visible_chunks:
                if chunks_rendered >= self.max_chunks_per_frame:
                    break
                    
                if key not in self.chunks:
                    self.chunks[key] = OptimizedChunk(key[0], key[1], self.chunk_size)
                
                chunk = self.chunks[key]
                # Skip if already rendered in immediate phase
                if chunk.dirty and chunk.needs_rerender(self.world_planner, base_tile_size):
                    chunk.render(self.world_planner, base_tile_size, self.sprite_cache)
                    chunks_rendered += 1
    
    def render_world_optimized(self, surface, camera_x, camera_y, zoom):
        """Optimized world rendering"""
        # Check if zoom changed
        if self.cached_zoom != zoom:
            self.invalidate_all_chunks()
            self.cached_zoom = zoom
        
        # Calculate effective tile size
        effective_tile_size = int(self.world_planner.tile_size * zoom)
        base_tile_size = self.world_planner.tile_size
        
        # Get visible chunks with optimization
        visible_chunks = self.get_visible_chunks_optimized(
            camera_x, camera_y,
            self.world_planner.canvas_rect.width,
            self.world_planner.canvas_rect.height,
            effective_tile_size
        )
        
        # Render chunks with optimization
        self.render_chunks_optimized(visible_chunks, base_tile_size)
        
        # Draw chunks to screen with optimization
        self.draw_chunks_to_screen_optimized(surface, visible_chunks, camera_x, camera_y, effective_tile_size)
    
    def draw_chunks_to_screen_optimized(self, surface, visible_chunks, camera_x, camera_y, effective_tile_size):
        """Fixed chunk drawing with proper rendering order and no overlaps"""
        world_width = self.world_planner.world_width
        world_height = self.world_planner.world_height
        max_chunk_x = (world_width - 1) // self.chunk_size
        max_chunk_y = (world_height - 1) // self.chunk_size
        
        # Pre-calculate screen bounds for culling
        screen_left = self.world_planner.toolbar_width + self.world_planner.resize_handle_width
        screen_right = self.world_planner.screen_width
        screen_top = 0
        screen_bottom = self.world_planner.screen_height
        
        base_tile_size = self.world_planner.tile_size
        
        # FIXED: Sort chunks for consistent left-to-right, top-to-bottom rendering
        sorted_chunks = sorted(visible_chunks, key=lambda chunk: (chunk[1], chunk[0]))  # Sort by Y first, then X
        
        # Batch similar operations
        chunks_to_draw = []
        
        for key in sorted_chunks:
            chunk_x, chunk_y = key
            
            # Skip chunks outside world bounds
            if not (0 <= chunk_x <= max_chunk_x and 0 <= chunk_y <= max_chunk_y):
                continue
            
            if key not in self.chunks or self.chunks[key].surface is None:
                continue
            
            chunk = self.chunks[key]
            
            # FIXED: Calculate screen position for MAIN area only (no border)
            main_screen_x = (chunk.x * self.chunk_size * effective_tile_size - 
                            camera_x + screen_left)
            main_screen_y = (chunk.y * self.chunk_size * effective_tile_size - camera_y)
            
            # Calculate main chunk size (without border)
            main_chunk_pixel_size = self.chunk_size * effective_tile_size
            
            # Frustum culling - skip chunks completely outside screen
            if (main_screen_x + main_chunk_pixel_size < screen_left or main_screen_x > screen_right or
                main_screen_y + main_chunk_pixel_size < screen_top or main_screen_y > screen_bottom):
                continue
            
            chunks_to_draw.append((chunk, main_screen_x, main_screen_y, main_chunk_pixel_size))
        
        # Draw chunks in batch with NO OVERLAPS
        for chunk, screen_x, screen_y, chunk_pixel_size in chunks_to_draw:
            self.draw_chunk_main_area_only(surface, chunk, screen_x, screen_y, chunk_pixel_size, 
                                        base_tile_size, effective_tile_size)
