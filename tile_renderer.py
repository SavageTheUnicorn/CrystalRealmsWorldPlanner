import pygame
import math
import json
import os
from constants import TileConnection


class OptimizedTileRenderer:
    """Optimized tile renderer with performance improvements"""
    
    def __init__(self, block_manager):
        self.block_manager = block_manager
        self.rules_engine = RulesEngine()
        
        # Performance caches
        self.sprite_cache = {}  # Cache for processed sprites
        self.tile_info_cache = {}  # Cache for tile variant calculations
        self.neighbor_cache = {}  # Cache for neighbor lookups
        
        # Batch processing
        self.batch_operations = []
        self.current_layer = None
        
        # Pre-converted sprites for faster blitting
        self.converted_sprites = {}
    
    def get_converted_sprite(self, sprite):
        """Get a sprite converted to display format for faster blitting"""
        sprite_id = id(sprite)
        
        if sprite_id not in self.converted_sprites:
            if sprite.get_flags() & pygame.SRCALPHA:
                converted = sprite.convert_alpha()
            else:
                converted = sprite.convert()
            self.converted_sprites[sprite_id] = converted
        
        return self.converted_sprites[sprite_id]
    
    def clear_caches(self):
        """Clear all caches (call when world changes significantly)"""
        self.sprite_cache.clear()
        self.tile_info_cache.clear()
        self.neighbor_cache.clear()
        self.converted_sprites.clear()
    
    def calculate_sprite_bounds(self, sprite, tile_mode):
        """Optimized sprite bounds calculation with caching"""
        if not sprite:
            return [(0, 0)]
        
        # Use sprite dimensions and tile mode as cache key
        cache_key = (sprite.get_width(), sprite.get_height(), tile_mode)
        
        if cache_key in self.sprite_cache:
            return self.sprite_cache[cache_key]
        
        bounds = self._calculate_sprite_bounds_impl(sprite, tile_mode)
        self.sprite_cache[cache_key] = bounds
        return bounds
    
    def _calculate_sprite_bounds_impl(self, sprite, tile_mode):
        """Implementation of sprite bounds calculation"""
        sprite_width = sprite.get_width()
        sprite_height = sprite.get_height()
        
        # Handle special rendering modes that use large sprite sheets but only occupy 1 tile
        if tile_mode in ['all', 'smaller_blocks', 'platform_enhanced', 'fence_enhanced', 'bedrock_pattern']:
            return [(0, 0)]
        
        # Handle contextual single-tile modes
        if tile_mode in ['vine', 'vertical']:
            return [(0, 0)]
        
        # Calculate tile dimensions using coverage-based approach
        bounds = []
        
        if tile_mode == 'log':
            return [(0, 0), (1, 0)]
                
        elif tile_mode in ['2state', '4state']:
            if tile_mode == '2state':
                actual_width = sprite_width // 2
            else:
                actual_width = sprite_width // 4
            
            tiles_wide = self.calculate_tiles_with_coverage(actual_width)
            tiles_tall = self.calculate_tiles_with_coverage(sprite_height)
            
            if tiles_wide == 1 and tiles_tall == 1:
                return [(0, 0)]
            
            for ty in range(tiles_tall):
                for tx in range(tiles_wide):
                    bounds.append((tx, -ty))
                    
        elif tile_mode == 'standard':
            if (sprite_width == 16 and sprite_height == 16) or (sprite_width == 32 and sprite_height == 32):
                return [(0, 0)]
            
            tiles_wide = self.calculate_tiles_with_coverage(sprite_width)
            tiles_tall = self.calculate_tiles_with_coverage(sprite_height)
            
            if tiles_wide == 1 and tiles_tall == 1:
                return [(0, 0)]
            
            for ty in range(tiles_tall):
                for tx in range(tiles_wide):
                    bounds.append((tx, -ty))
                    
        else:
            tiles_wide = self.calculate_tiles_with_coverage(sprite_width)
            tiles_tall = self.calculate_tiles_with_coverage(sprite_height)
            
            if tiles_wide == 1 and tiles_tall == 1:
                return [(0, 0)]
            
            for ty in range(tiles_tall):
                for tx in range(tiles_wide):
                    bounds.append((tx, -ty))
        
        return bounds if bounds else [(0, 0)]
    
    def calculate_tiles_with_coverage(self, dimension_pixels, coverage_threshold=0.5):
        """Calculate how many tiles are needed with coverage threshold"""
        if dimension_pixels <= 16:
            return 1
        
        complete_tiles = dimension_pixels // 16
        remainder = dimension_pixels % 16
        
        threshold_pixels = 16 * coverage_threshold
        if remainder > threshold_pixels:
            return complete_tiles + 1
        else:
            return complete_tiles
    
    def get_neighbor_block_type_cached(self, world_planner, tile_x, tile_y, direction, layer):
        """Cached neighbor lookup for better performance"""
        cache_key = (tile_x, tile_y, direction, layer, id(world_planner.layers[layer]))
        
        if cache_key in self.neighbor_cache:
            return self.neighbor_cache[cache_key]
        
        result = self.get_neighbor_block_type(world_planner, tile_x, tile_y, direction, layer)
        self.neighbor_cache[cache_key] = result
        return result
    
    def get_neighbor_block_type(self, world_planner, tile_x, tile_y, direction, layer):
        """Check neighboring blocks for a specific tile"""
        if direction is None:
            neighbor_pos = (tile_x, tile_y)
        else:
            offsets = {
                'top': (0, -1),
                'right': (1, 0),
                'bottom': (0, 1),
                'left': (-1, 0),
                'top_left': (-1, -1),
                'top_right': (1, -1),
                'bottom_left': (-1, 1),
                'bottom_right': (1, 1)
            }

            offset_x, offset_y = offsets[direction]
            neighbor_pos = (tile_x + offset_x, tile_y + offset_y)

        return world_planner.layers[layer].get(neighbor_pos, None)
    
    def get_tile_variant_cached(self, world_planner, tile_x, tile_y, block_data, layer):
        """Cached tile variant calculation"""
        # Create cache key from position, block data, and surrounding blocks
        block_id = block_data.get('id', '')
        tile_mode = block_data.get('tileMode', 'standard')
        
        # For complex tiling modes, include neighbor information in cache key
        if tile_mode in ['all', 'log', 'vine', 'vertical', 'smaller_blocks', 'platform_enhanced', 'fence_enhanced']:
            neighbors = []
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    neighbor = world_planner.layers[layer].get((tile_x + dx, tile_y + dy), None)
                    neighbor_id = neighbor.get('id', '') if neighbor else ''
                    neighbors.append(neighbor_id)
            cache_key = (tile_x, tile_y, block_id, tile_mode, tuple(neighbors))
        else:
            cache_key = (tile_x, tile_y, block_id, tile_mode)
        
        if cache_key in self.tile_info_cache:
            return self.tile_info_cache[cache_key]
        
        result = self.get_tile_variant(world_planner, tile_x, tile_y, block_data, layer)
        self.tile_info_cache[cache_key] = result
        return result
    
    def get_tile_variant(self, world_planner, tile_x, tile_y, block_data, layer):
        """Determine which sprite variant to use for tileable blocks"""
        if not block_data.get('tileSet', False):
            return 'center'
    
        tile_mode = block_data.get('tileMode', 'standard')
        
        if tile_mode == 'standard':
            return 'center'
    
        # Use specialized tiling logic based on the tile mode
        if tile_mode == 'log':
            return self.get_log_tile_info(world_planner, tile_x, tile_y, block_data, layer)
        elif tile_mode == 'all':
            return self.get_all_tile_info(world_planner, tile_x, tile_y, block_data, layer)
        elif tile_mode == 'vertical':
            return self.get_vertical_tile_info(world_planner, tile_x, tile_y, block_data, layer)
        elif tile_mode == 'vine':
            return self.get_vine_tile_info(world_planner, tile_x, tile_y, block_data, layer)
        elif tile_mode == '2state':
            return self.get_2state_tile_info(world_planner, tile_x, tile_y, block_data, layer)
        elif tile_mode == '4state':
            return self.get_4state_tile_info(world_planner, tile_x, tile_y, block_data, layer)
        elif tile_mode == 'smaller_blocks':
            return self.get_smaller_blocks_tile_info(world_planner, tile_x, tile_y, block_data, layer)
        elif tile_mode == 'platform_enhanced':
            return self.get_platform_enhanced_tile_info(world_planner, tile_x, tile_y, block_data, layer)
        elif tile_mode == 'fence_enhanced':
            return self.get_fence_enhanced_tile_info(world_planner, tile_x, tile_y, block_data, layer)
        elif tile_mode == 'bedrock_pattern':
            return self.get_bedrock_pattern_tile_info(world_planner, tile_x, tile_y, block_data, layer)
    
        return 'center'
    
    def draw_block_optimized(self, surface, world_planner, tile_x, tile_y, block_data, screen_x, screen_y, size, layer):
        """Optimized block drawing method"""
        block_id = block_data.get('id', '')
        sprite = self.block_manager.get_sprite(block_id)
        tile_mode = block_data.get('tileMode', 'standard')
        
        # Convert coordinates to integers early
        int_screen_x = int(screen_x)
        int_screen_y = int(screen_y)
        int_size = int(size)
    
        if not sprite:
            # Fallback to color
            block_def = self.block_manager.get_block_by_id(block_id)
            if block_def:
                color = block_def.get('color', (128, 128, 128))
                pygame.draw.rect(surface, color, (int_screen_x, int_screen_y, int_size, int_size))
            return
        
        # Get converted sprite for faster blitting
        sprite = self.get_converted_sprite(sprite)
        
        # Handle different rendering modes
        if tile_mode == 'standard':
            self.draw_standard_sprite_optimized(surface, sprite, int_screen_x, int_screen_y, int_size)
            
        elif tile_mode in ['all', 'log', 'vertical', 'vine', '2state', '4state', 'smaller_blocks', 'platform_enhanced', 'fence_enhanced', 'bedrock_pattern']:
            # Get cached tile info
            tile_info = self.get_tile_variant_cached(world_planner, tile_x, tile_y, block_data, layer)
            if isinstance(tile_info, dict):
                self.draw_specialized_sprite_optimized(surface, sprite, tile_info, int_screen_x, int_screen_y, int_size)
            else:
                self.draw_standard_sprite_optimized(surface, sprite, int_screen_x, int_screen_y, int_size)
        else:
            self.draw_standard_sprite_optimized(surface, sprite, int_screen_x, int_screen_y, int_size)
        
        # Draw borders if needed (optimized)
        if hasattr(world_planner, 'show_borders') and world_planner.show_borders:
            self.draw_borders_if_needed_optimized(surface, world_planner, tile_x, tile_y, block_data, int_screen_x, int_screen_y, int_size, layer)
    
    def draw_standard_sprite_optimized(self, surface, sprite, screen_x, screen_y, size):
        """Optimized standard sprite drawing"""
        sprite_width = sprite.get_width()
        sprite_height = sprite.get_height()
        
        # Fast path for common sizes
        if sprite_width == 16 and sprite_height == 16 and size == 16:
            surface.blit(sprite, (screen_x, screen_y))
            return
            
        if sprite_width == 32 and sprite_height == 32 and size == 32:
            surface.blit(sprite, (screen_x, screen_y))
            return
    
        # Special case: center 4x4 sprite in tile
        if sprite_width == 4 and sprite_height == 4:
            offset_x = screen_x + (size // 2 - 2)
            offset_y = screen_y + (size // 2 - 2)
            surface.blit(sprite, (offset_x, offset_y))
            return
        
        # Special case: center 11x11 sprite in tile
        if sprite_width == 11 and sprite_height == 11:
            offset_x = screen_x + (size // 2 - 5)
            offset_y = screen_y + (size // 2 - 5)
            surface.blit(sprite, (offset_x, offset_y))
            return
        
        # Calculate scaling
        if sprite_width == 16 and sprite_height == 16:
            if size != 16:
                try:
                    scaled_sprite = pygame.transform.scale(sprite, (size, size))
                    surface.blit(scaled_sprite, (screen_x, screen_y))
                except:
                    surface.blit(sprite, (screen_x, screen_y))
            else:
                surface.blit(sprite, (screen_x, screen_y))
            return
            
        elif sprite_width == 32 and sprite_height == 32:
            if size != 32:
                try:
                    scaled_sprite = pygame.transform.scale(sprite, (size, size))
                    surface.blit(scaled_sprite, (screen_x, screen_y))
                except:
                    surface.blit(sprite, (screen_x, screen_y))
            else:
                surface.blit(sprite, (screen_x, screen_y))
            return
        
        # General case
        exact_tiles_wide = sprite_width / 16
        exact_tiles_tall = sprite_height / 16
        
        scaled_width = int(exact_tiles_wide * size)
        scaled_height = int(exact_tiles_tall * size)
        
        try:
            if scaled_width != sprite_width or scaled_height != sprite_height:
                if scaled_width > sprite_width or scaled_height > sprite_height:
                    scaled_sprite = pygame.transform.smoothscale(sprite, (scaled_width, scaled_height))
                else:
                    scaled_sprite = pygame.transform.scale(sprite, (scaled_width, scaled_height))
            else:
                scaled_sprite = sprite
        except:
            scaled_sprite = sprite
        
        # Position with bottom-left as origin for tall sprites
        adj_screen_y = screen_y + size - scaled_height
        surface.blit(scaled_sprite, (screen_x, adj_screen_y))
    
    def draw_specialized_sprite_optimized(self, surface, sprite, tile_info, screen_x, screen_y, size):
        """Optimized specialized sprite drawing"""
        tile_type = tile_info.get('type')
        
        # Use a lookup table for faster dispatch
        sprite_drawers = {
            'all': self.draw_all_sprite_optimized,
            'log': self.draw_log_sprite_optimized,
            'vertical': self.draw_vertical_sprite_optimized,
            'vine': self.draw_vine_sprite_optimized,
            '2state': self.draw_2state_sprite_optimized,
            '4state': self.draw_4state_sprite_optimized,
            'smaller_blocks': self.draw_smaller_blocks_sprite_optimized,
            'platform_enhanced': self.draw_platform_enhanced_sprite_optimized,
            'fence_enhanced': self.draw_fence_enhanced_sprite_optimized,
            'bedrock_pattern': self.draw_bedrock_pattern_sprite_optimized
        }
        
        drawer = sprite_drawers.get(tile_type)
        if drawer:
            drawer(surface, sprite, tile_info, screen_x, screen_y, size)
        else:
            self.draw_standard_sprite_optimized(surface, sprite, screen_x, screen_y, size)
    
    def draw_borders_if_needed_optimized(self, surface, world_planner, tile_x, tile_y, block_data, screen_x, screen_y, size, layer):
        """Optimized border drawing"""
        if not block_data.get('tileSet', False):
            # Draw full border for non-tileable blocks
            border_color = (0, 0, 0, 120)
            pygame.draw.rect(surface, border_color, (screen_x, screen_y, size, size), 1)
            return
        
        tileable = block_data.get('tileable', {})
        if not any(tileable.values()):
            return  # No tileable directions
        
        # Check neighbors efficiently
        block_id = block_data.get('id', '')
        layer_dict = world_planner.layers[layer]
        
        # Pre-calculate neighbor positions
        neighbor_positions = {
            'top': (tile_x, tile_y - 1),
            'right': (tile_x + 1, tile_y),
            'bottom': (tile_x, tile_y + 1),
            'left': (tile_x - 1, tile_y)
        }
        
        same_neighbors = []
        border_color = (0, 0, 0, 80) if block_data.get('isBackground', False) else (0, 0, 0, 120)
        
        for direction, pos in neighbor_positions.items():
            if not tileable.get(direction, False):
                continue
                
            neighbor = layer_dict.get(pos, None)
            if neighbor and neighbor.get('id', '') == block_id:
                same_neighbors.append(direction)
        
        # Draw borders only where needed
        if len(same_neighbors) < 4:  # Not all directions have same neighbors
            border_lines = []
            
            if 'top' not in same_neighbors:
                border_lines.extend([(screen_x, screen_y), (screen_x + size, screen_y)])
            if 'right' not in same_neighbors:
                border_lines.extend([(screen_x + size, screen_y), (screen_x + size, screen_y + size)])
            if 'bottom' not in same_neighbors:
                border_lines.extend([(screen_x, screen_y + size), (screen_x + size, screen_y + size)])
            if 'left' not in same_neighbors:
                border_lines.extend([(screen_x, screen_y), (screen_x, screen_y + size)])
            
            if border_lines:
                pygame.draw.lines(surface, border_color, False, border_lines)
    
    def draw_vine_sprite_optimized(self, surface, sprite, tile_info, screen_x, screen_y, size):
        """Optimized vine sprite drawing"""
        neighbors = tile_info.get('neighbors', {})
        up = neighbors.get('up', False)
        down = neighbors.get('down', False)
        alternation = tile_info.get('alternation', False)
        
        sprite_width = sprite.get_width()
        sprite_height = sprite.get_height()
        
        try:
            alt_offset = 8 if alternation else 0
            
            if up and down:
                src_rect = pygame.Rect(0, 16 + alt_offset, 16, 16)
            elif up:
                src_rect = pygame.Rect(0, 24 + alt_offset, 16, 16)
            else:
                src_rect = pygame.Rect(0, 0 + alt_offset, 16, 16)
            
            # Bounds checking
            if (src_rect.right <= sprite_width and src_rect.bottom <= sprite_height and
                src_rect.x >= 0 and src_rect.y >= 0):
                
                vine_slice = sprite.subsurface(src_rect)
                if size != 16:
                    scaled_slice = pygame.transform.scale(vine_slice, (size, size))
                    surface.blit(scaled_slice, (screen_x, screen_y))
                else:
                    surface.blit(vine_slice, (screen_x, screen_y))
            else:
                # Fallback
                self.draw_standard_sprite_optimized(surface, sprite, screen_x, screen_y, size)
                
        except Exception:
            # Emergency fallback
            self.draw_standard_sprite_optimized(surface, sprite, screen_x, screen_y, size)
    
    def draw_log_sprite_optimized(self, surface, sprite, tile_info, screen_x, screen_y, size):
        """Optimized log sprite drawing"""
        up, down = tile_info.get('state', (False, False))
        is_odd_row = tile_info.get('is_odd_row', False)
        
        dx = 32 if is_odd_row else 0
        
        # Determine sprite rectangle
        if up and down:
            sprite_rect = pygame.Rect(64 + dx, 0, 32, 16)
        elif up:
            sprite_rect = pygame.Rect(0 + dx, 24, 32, 16)
        elif down:
            sprite_rect = pygame.Rect(0 + dx, 0, 32, 24)
        else:
            sprite_rect = pygame.Rect(64 + dx, 16, 32, 24)
        
        try:
            if (sprite.get_width() >= sprite_rect.width + sprite_rect.x and 
                sprite.get_height() >= sprite_rect.height + sprite_rect.y):
                
                log_slice = sprite.subsurface(sprite_rect)
                
                # Scale to 2 tiles wide, proportional height
                log_width = size * 2
                log_height = int(size * 1.5)
                
                if log_slice.get_size() != (log_width, log_height):
                    scaled_slice = pygame.transform.scale(log_slice, (log_width, log_height))
                else:
                    scaled_slice = log_slice
                
                # Position the log sprite
                log_y = screen_y + size - log_height
                surface.blit(scaled_slice, (screen_x, log_y))
            else:
                # Fallback
                self.draw_standard_sprite_optimized(surface, sprite, screen_x, screen_y, size)
                
        except Exception:
            # Emergency fallback
            pygame.draw.rect(surface, (139, 90, 43), (screen_x - size // 2, screen_y, size * 2, size))
    
    def check_neighbor(self, world_planner, tile_x, tile_y, dx, dy, block_id, layer):
        """Check if neighbor at offset (dx, dy) has the same block ID"""
        neighbor = self.get_neighbor_block_type(world_planner, tile_x + dx, tile_y + dy, None, layer)
        return neighbor and neighbor.get('id', '') == block_id
    
    def get_all_tile_info(self, world_planner, tile_x, tile_y, block_data, layer):
        """FIXED: Proper autotiling logic matching Rust implementation"""
        block_id = block_data.get('id', '')
    
        # Check the 4 orthogonal neighbors
        left = self.check_neighbor(world_planner, tile_x, tile_y, -1, 0, block_id, layer)
        right = self.check_neighbor(world_planner, tile_x, tile_y, 1, 0, block_id, layer)
        up = self.check_neighbor(world_planner, tile_x, tile_y, 0, -1, block_id, layer)
        down = self.check_neighbor(world_planner, tile_x, tile_y, 0, 1, block_id, layer)
        
        # CRITICAL: Only check diagonal neighbors when their adjacent orthogonal neighbors exist
        # This matches the Rust logic exactly
        up_left = False
        up_right = False
        down_left = False
        down_right = False
        
        # Only check up_left if both up AND left neighbors exist
        if up and left:
            up_left = self.check_neighbor(world_planner, tile_x, tile_y, -1, -1, block_id, layer)
        
        # Only check up_right if both up AND right neighbors exist  
        if up and right:
            up_right = self.check_neighbor(world_planner, tile_x, tile_y, 1, -1, block_id, layer)
        
        # Only check down_left if both down AND left neighbors exist
        if down and left:
            down_left = self.check_neighbor(world_planner, tile_x, tile_y, -1, 1, block_id, layer)
        
        # Only check down_right if both down AND right neighbors exist
        if down and right:
            down_right = self.check_neighbor(world_planner, tile_x, tile_y, 1, 1, block_id, layer)
    
        # Use consistent alternation pattern (matching Rust % 2 logic)
        is_odd_column = tile_x % 2 == 1
        is_odd_row = tile_y % 2 == 1
    
        return {
            'type': 'all',
            'neighbors': {
                'left': left, 'right': right, 'up': up, 'down': down,
                'up_left': up_left, 'up_right': up_right,
                'down_left': down_left, 'down_right': down_right
            },
            'is_odd_column': is_odd_column,
            'is_odd_row': is_odd_row
        }
    
    def get_log_tile_info(self, world_planner, tile_x, tile_y, block_data, layer):
        """Get tile info for log-type blocks"""
        up_block = self.get_neighbor_block_type(world_planner, tile_x, tile_y, 'top', layer)
        down_block = self.get_neighbor_block_type(world_planner, tile_x, tile_y, 'bottom', layer)

        up = up_block and up_block.get('id', '') == block_data.get('id', '')
        down = down_block and down_block.get('id', '') == block_data.get('id', '')
        is_odd_row = tile_y % 2 == 1

        return {
            'type': 'log',
            'state': (up, down),
            'is_odd_row': is_odd_row
        }
    
    def get_vertical_tile_info(self, world_planner, tile_x, tile_y, block_data, layer):
        """Get tile info for vertical growth sprites (like cactus)"""
        block_id = block_data.get('id', '')
        up_block = world_planner.layers[layer].get((tile_x, tile_y - 1), None)
        down_block = world_planner.layers[layer].get((tile_x, tile_y + 1), None)
        
        up = up_block is not None and up_block.get('id', '') == block_id
        down = down_block is not None and down_block.get('id', '') == block_id
    
        return {
            'type': 'vertical',
            'neighbors': {'up': up, 'down': down}
        }
    
    def get_vine_tile_info(self, world_planner, tile_x, tile_y, block_data, layer):
        """Get tile info for vine sprites"""
        block_id = block_data.get('id', '')
        up_block = world_planner.layers[layer].get((tile_x, tile_y - 1), None)
        down_block = world_planner.layers[layer].get((tile_x, tile_y + 1), None)
        
        def is_solid_for_vine(block):
            if block is None:
                return False
            if block.get('id', '') == block_id:
                return True
            if not block.get('isBackground', False) and block.get('tileSet', False):
                return True
            block_category = block.get('category', '')
            if block_category in ['terrain', 'interactive']:
                return True
            solid_block_ids = ['dirt', 'stone', 'wood', 'brick', 'cobblestone', 'clay', 'obsidian']
            if any(solid_id in block.get('id', '').lower() for solid_id in solid_block_ids):
                return True
            return False
        
        up = is_solid_for_vine(up_block)
        down = is_solid_for_vine(down_block)
        alternation = (tile_x + tile_y) % 2 == 1
    
        return {
            'type': 'vine',
            'neighbors': {'up': up, 'down': down},
            'alternation': alternation
        }
    
    # Include other tile info methods as needed...
    def get_2state_tile_info(self, world_planner, tile_x, tile_y, block_data, layer):
        """Get tile info for 2-state sprites"""
        return {
            'type': '2state',
            'state': block_data.get('state', 0),
            'stateCount': block_data.get('stateCount', 2)
        }

    def get_4state_tile_info(self, world_planner, tile_x, tile_y, block_data, layer):
        """Get tile info for 4-state sprites"""
        return {
            'type': '4state',
            'state': block_data.get('state', 0),
            'stateCount': block_data.get('stateCount', 4)
        }
    
    def get_smaller_blocks_tile_info(self, world_planner, tile_x, tile_y, block_data, layer):
        """Get tile info for smaller_blocks sprites"""
        block_id = block_data.get('id', '')
        
        left = self.check_neighbor(world_planner, tile_x, tile_y, -1, 0, block_id, layer)
        right = self.check_neighbor(world_planner, tile_x, tile_y, 1, 0, block_id, layer)
        up = self.check_neighbor(world_planner, tile_x, tile_y, 0, -1, block_id, layer)
        down = self.check_neighbor(world_planner, tile_x, tile_y, 0, 1, block_id, layer)
        down_left = self.check_neighbor(world_planner, tile_x, tile_y, -1, 1, block_id, layer)
        down_right = self.check_neighbor(world_planner, tile_x, tile_y, 1, 1, block_id, layer)
        
        return {
            'type': 'smaller_blocks',
            'neighbors': {
                'left': left, 'right': right, 'up': up, 'down': down,
                'down_left': down_left, 'down_right': down_right
            }
        }
    
    def get_platform_enhanced_tile_info(self, world_planner, tile_x, tile_y, block_data, layer):
        """Get tile info for enhanced platform sprites"""
        block_id = block_data.get('id', '')
        left = self.check_neighbor(world_planner, tile_x, tile_y, -1, 0, block_id, layer)
        right = self.check_neighbor(world_planner, tile_x, tile_y, 1, 0, block_id, layer)
    
        return {
            'type': 'platform_enhanced',
            'neighbors': {'left': left, 'right': right},
            'is_odd_column': tile_x % 2 == 1
        }
    
    def get_fence_enhanced_tile_info(self, world_planner, tile_x, tile_y, block_data, layer):
        """Get tile info for enhanced fence sprites"""
        block_id = block_data.get('id', '')
        left = self.check_neighbor(world_planner, tile_x, tile_y, -1, 0, block_id, layer)
        right = self.check_neighbor(world_planner, tile_x, tile_y, 1, 0, block_id, layer)
    
        return {
            'type': 'fence_enhanced',
            'neighbors': {'left': left, 'right': right},
            'is_odd_column': tile_x % 2 == 1
        }
    
    def get_bedrock_pattern_tile_info(self, world_planner, tile_x, tile_y, block_data, layer):
        """Get tile info for bedrockandwater sprites"""
        return {
            'type': 'bedrock_pattern',
            'is_odd_column': tile_x % 2 == 1,
            'is_odd_row': tile_y % 2 == 1
        }
    
    def draw_all_sprite_optimized(self, surface, sprite, tile_info, screen_x, screen_y, size):
        """FIXED: 'all' mode sprites matching the Rust implementation exactly"""
        neighbors = tile_info.get('neighbors', {})
        left = neighbors.get('left', False)
        right = neighbors.get('right', False)
        up = neighbors.get('up', False)
        down = neighbors.get('down', False)
        up_left = neighbors.get('up_left', False)
        up_right = neighbors.get('up_right', False)
        down_left = neighbors.get('down_left', False)
        down_right = neighbors.get('down_right', False)
    
        is_odd_column = tile_info.get('is_odd_column', False)
        is_odd_row = tile_info.get('is_odd_row', False)
        
        # Create 16x24 tile surface (matches Rust implementation)
        tile_surface = pygame.Surface((16, 24), pygame.SRCALPHA)
        tile_surface = tile_surface.convert_alpha()
        
        # Calculate sprite sheet offsets (matching Rust dx, dy1, dy2, dy3)
        dx = 16 if is_odd_column else 0
        dy1 = 16 if is_odd_row else 0
        dy2 = 24 if is_odd_row else 0
        dy3 = 24 if not is_odd_row else 0
    
        try:
            # Check for fully surrounded tile (single sprite case)
            all_neighbors = all([left, right, up, down, up_left, up_right, down_left, down_right])
            
            if all_neighbors:
                # Single sprite for fully surrounded tiles: 128+dx, 0+dy1, 16x16 -> place at (0,8)
                # This should NOT be stretched - use 16x16 sprite as-is
                sprite_rect = pygame.Rect(128 + dx, 0 + dy1, 16, 16)
                if (sprite.get_width() >= sprite_rect.right and 
                    sprite.get_height() >= sprite_rect.bottom):
                    single_slice = sprite.subsurface(sprite_rect)
                    # Place the 16x16 sprite at y=8 to fill the main connection area
                    # Don't stretch it to 16x24 - keep it as 16x16
                    tile_surface.blit(single_slice, (0, 8))
                else:
                    tile_surface.fill((255, 0, 255))  # Error color
            else:
                # Render segments with correct positioning based on segment size
                # 8x16 segments (corners/edges with no neighbor above) go at y=0
                # 8x8 segments (interior with neighbor above) go at y=8 to fill bottom half
                
                # TOP-LEFT segment 
                if not left and not up:
                    # Corner: extract 8x16, place at TOP (0,0) - fills full height
                    src_rect = pygame.Rect(0 + dx, 0 + dy2, 8, 16)
                    dest_y = 0
                elif not up:
                    # Top edge: extract 8x16, place at TOP (0,0) - fills full height
                    src_rect = pygame.Rect(32 + dx, 0 + dy2, 8, 16)
                    dest_y = 0
                elif not left:
                    # Left edge: extract 8x8, place at (0,8) - fills bottom half of top area
                    src_rect = pygame.Rect(96 + dx, 0 + dy1, 8, 8)
                    dest_y = 8
                elif not up_left:
                    # Inner corner: extract 8x8, place at (0,8) - fills bottom half of top area
                    src_rect = pygame.Rect(64 + dx, 8 + dy2, 8, 8)
                    dest_y = 8
                else:
                    # Interior: extract 8x8, place at (0,8) - fills bottom half of top area
                    src_rect = pygame.Rect(128 + dx, 0 + dy1, 8, 8)
                    dest_y = 8
                
                if (sprite.get_width() >= src_rect.right and 
                    sprite.get_height() >= src_rect.bottom):
                    tile_surface.blit(sprite.subsurface(src_rect), (0, dest_y))
    
                # TOP-RIGHT segment
                if not right and not up:
                    # Corner: extract 8x16, place at TOP (8,0) - fills full height
                    src_rect = pygame.Rect(8 + dx, 0 + dy2, 8, 16)
                    dest_y = 0
                elif not up:
                    # Top edge: extract 8x16, place at TOP (8,0) - fills full height
                    src_rect = pygame.Rect(40 + dx, 0 + dy2, 8, 16)
                    dest_y = 0
                elif not right:
                    # Right edge: extract 8x8, place at (8,8) - fills bottom half of top area
                    src_rect = pygame.Rect(104 + dx, 0 + dy1, 8, 8)
                    dest_y = 8
                elif not up_right:
                    # Inner corner: extract 8x8, place at (8,8) - fills bottom half of top area
                    src_rect = pygame.Rect(72 + dx, 8 + dy2, 8, 8)
                    dest_y = 8
                else:
                    # Interior: extract 8x8, place at (8,8) - fills bottom half of top area
                    src_rect = pygame.Rect(136 + dx, 0 + dy1, 8, 8)
                    dest_y = 8
                
                if (sprite.get_width() >= src_rect.right and 
                    sprite.get_height() >= src_rect.bottom):
                    tile_surface.blit(sprite.subsurface(src_rect), (8, dest_y))
    
                # BOTTOM-LEFT segment (dirt at bottom of tile) - always at y=16
                if not left and not down:
                    src_rect = pygame.Rect(0 + dx, 16 + dy2, 8, 8)
                elif not down:
                    src_rect = pygame.Rect(32 + dx, 16 + dy2, 8, 8)
                elif not left and not down_left:
                    src_rect = pygame.Rect(96 + dx, 8 + dy1, 8, 8)
                elif not left and down_left:
                    src_rect = pygame.Rect(64 + dx, 0 + dy3, 8, 8)
                elif not down_left:
                    src_rect = pygame.Rect(64 + dx, 16 + dy2, 8, 8)
                else:
                    src_rect = pygame.Rect(128 + dx, 8 + dy1, 8, 8)
                
                if (sprite.get_width() >= src_rect.right and 
                    sprite.get_height() >= src_rect.bottom):
                    tile_surface.blit(sprite.subsurface(src_rect), (0, 16))
    
                # BOTTOM-RIGHT segment (dirt at bottom of tile) - always at y=16
                if not right and not down:
                    src_rect = pygame.Rect(8 + dx, 16 + dy2, 8, 8)
                elif not down:
                    src_rect = pygame.Rect(40 + dx, 16 + dy2, 8, 8)
                elif not right and not down_right:
                    src_rect = pygame.Rect(104 + dx, 8 + dy1, 8, 8)
                elif not right and down_right:
                    src_rect = pygame.Rect(72 + dx, 0 + dy3, 8, 8)
                elif not down_right:
                    src_rect = pygame.Rect(72 + dx, 16 + dy2, 8, 8)
                else:
                    src_rect = pygame.Rect(136 + dx, 8 + dy1, 8, 8)
                
                if (sprite.get_width() >= src_rect.right and 
                    sprite.get_height() >= src_rect.bottom):
                    tile_surface.blit(sprite.subsurface(src_rect), (8, 16))
    
            # Scale and position the final 16x24 tile
            if size == 16:
                # Render the full 16x24 tile, positioned so the bottom 16px align with the grid
                # This allows the top 8px (grass) to extend above the grid line naturally
                surface.blit(tile_surface, (screen_x, screen_y - 8))
            else:
                # Scale maintaining 16:24 aspect ratio
                final_width = size
                final_height = int(size * 1.5)  # 24/16 = 1.5
                
                scaled_tile = pygame.transform.scale(tile_surface, (final_width, final_height))
                # Position so the bottom portion aligns with the grid cell
                # The extra height extends upward like grass/details
                adj_screen_y = screen_y - int(size * 0.5)  # Offset by the extra height
                surface.blit(scaled_tile, (screen_x, adj_screen_y))
    
        except Exception as e:
            print(f"Error in fixed 'all' sprite rendering: {e}")
            # Fallback to error rectangle
            pygame.draw.rect(surface, (255, 0, 255), (screen_x, screen_y, size, size))
    
    def draw_vertical_sprite_optimized(self, surface, sprite, tile_info, screen_x, screen_y, size):
        """Optimized vertical sprite drawing - FIXED part positioning"""
        neighbors = tile_info.get('neighbors', {})
        up = neighbors.get('up', False)
        down = neighbors.get('down', False)
        
        try:
            if not up and not down:
                # Single: src(0,0,16,24) at dest(0,0)
                sprite_rect = pygame.Rect(0, 0, 16, 24)
                if sprite.get_width() >= 16 and sprite.get_height() >= 24:
                    single_slice = sprite.subsurface(sprite_rect)
                    scaled_height = int(size * 1.5)
                    scaled_slice = pygame.transform.scale(single_slice, (size, scaled_height))
                    surface.blit(scaled_slice, (screen_x, screen_y + size - scaled_height))
                    return
                    
            elif up and down:
                # Middle: src(0,24,16,40) at dest(0,0) = src(0,24,16,16)
                sprite_rect = pygame.Rect(0, 24, 16, 16)
                if sprite.get_width() >= 16 and sprite.get_height() >= 40:
                    middle_slice = sprite.subsurface(sprite_rect)
                    scaled_slice = pygame.transform.scale(middle_slice, (size, size))
                    surface.blit(scaled_slice, (screen_x, screen_y))
                    return
                    
            elif up:
                # Bottom of stack: SWAPPED POSITIONS
                if sprite.get_width() >= 16 and sprite.get_height() >= 32:
                    tile_surface = pygame.Surface((size, size), pygame.SRCALPHA)
                    tile_surface.fill((0, 0, 0, 0))
                    
                    # Part 1: src(0,24,16,8) at dest(0,0) - TOP HALF
                    part1_rect = pygame.Rect(0, 24, 16, 8)
                    part1_slice = sprite.subsurface(part1_rect)
                    part1_scaled = pygame.transform.scale(part1_slice, (size, size // 2))
                    tile_surface.blit(part1_scaled, (0, 0))
                    
                    # Part 2: src(0,16,16,8) at dest(0,size//2) - BOTTOM HALF
                    part2_rect = pygame.Rect(0, 16, 16, 8)
                    part2_slice = sprite.subsurface(part2_rect)
                    part2_scaled = pygame.transform.scale(part2_slice, (size, size // 2))
                    tile_surface.blit(part2_scaled, (0, size // 2))
                    
                    surface.blit(tile_surface, (screen_x, screen_y))
                    return
                    
            else:  # down only
                # Top of stack: SWAPPED POSITIONS
                if sprite.get_width() >= 16 and sprite.get_height() >= 40:
                    tile_surface = pygame.Surface((size, size), pygame.SRCALPHA)
                    tile_surface.fill((0, 0, 0, 0))
                    
                    # Part 1: src(0,0,16,16) at dest(0,0) - TOP HALF (scaled to half height)
                    part1_rect = pygame.Rect(0, 0, 16, 16)
                    part1_slice = sprite.subsurface(part1_rect)
                    part1_scaled = pygame.transform.scale(part1_slice, (size, size // 2))
                    tile_surface.blit(part1_scaled, (0, 0))
                    
                    # Part 2: src(0,32,16,8) at dest(0,size//2) - BOTTOM HALF
                    part2_rect = pygame.Rect(0, 32, 16, 8)
                    part2_slice = sprite.subsurface(part2_rect)
                    part2_scaled = pygame.transform.scale(part2_slice, (size, size // 2))
                    tile_surface.blit(part2_scaled, (0, size // 2))
                    
                    surface.blit(tile_surface, (screen_x, screen_y))
                    return
                    
        except Exception:
            pass
        
        # Fallback
        self.draw_standard_sprite_optimized(surface, sprite, screen_x, screen_y, size)
    
    def draw_2state_sprite_optimized(self, surface, sprite, tile_info, screen_x, screen_y, size):
        """Optimized 2-state sprite drawing"""
        state = tile_info.get('state', 0)
        state_count = tile_info.get('stateCount', 2)
        
        sprite_width = sprite.get_width()
        section_width = sprite_width // state_count
        sprite_height = sprite.get_height()
        
        src_x = state * section_width
        src_rect = pygame.Rect(src_x, 0, section_width, sprite_height)
        
        try:
            state_sprite = sprite.subsurface(src_rect)
            
            # Calculate proper multi-tile scaling
            exact_tiles_wide = section_width / 16
            exact_tiles_tall = sprite_height / 16
            
            scaled_width = int(exact_tiles_wide * size)
            scaled_height = int(exact_tiles_tall * size)
            
            if (scaled_width, scaled_height) != state_sprite.get_size():
                scaled_sprite = pygame.transform.scale(state_sprite, (scaled_width, scaled_height))
                # Position with bottom-left as origin for tall sprites
                adj_screen_y = screen_y + size - scaled_height
                surface.blit(scaled_sprite, (screen_x, adj_screen_y))
            else:
                adj_screen_y = screen_y + size - scaled_height
                surface.blit(state_sprite, (screen_x, adj_screen_y))
        except Exception:
            pygame.draw.rect(surface, (255, 0, 255), (screen_x, screen_y, size, size))
    
    def draw_4state_sprite_optimized(self, surface, sprite, tile_info, screen_x, screen_y, size):
        """Optimized 4-state sprite drawing"""
        state = tile_info.get('state', 0)
        state_count = tile_info.get('stateCount', 4)
        
        sprite_width = sprite.get_width()
        section_width = sprite_width // state_count
        sprite_height = sprite.get_height()
        
        src_x = state * section_width
        src_rect = pygame.Rect(src_x, 0, section_width, sprite_height)
        
        try:
            state_sprite = sprite.subsurface(src_rect)
            
            # Calculate proper multi-tile scaling
            exact_tiles_wide = section_width / 16
            exact_tiles_tall = sprite_height / 16
            
            scaled_width = int(exact_tiles_wide * size)
            scaled_height = int(exact_tiles_tall * size)
            
            if (scaled_width, scaled_height) != state_sprite.get_size():
                scaled_sprite = pygame.transform.scale(state_sprite, (scaled_width, scaled_height))
                # Position with bottom-left as origin for tall sprites
                adj_screen_y = screen_y + size - scaled_height
                surface.blit(scaled_sprite, (screen_x, adj_screen_y))
            else:
                adj_screen_y = screen_y + size - scaled_height
                surface.blit(state_sprite, (screen_x, adj_screen_y))
        except Exception:
            pygame.draw.rect(surface, (255, 0, 255), (screen_x, screen_y, size, size))
    
    def draw_smaller_blocks_sprite_optimized(self, surface, sprite, tile_info, screen_x, screen_y, size):
        """FIXED smaller_blocks: properly handles segment scaling to prevent stretching"""
        neighbors = tile_info.get('neighbors', {})
        left = neighbors.get('left', False)
        right = neighbors.get('right', False)
        up = neighbors.get('up', False)
        down = neighbors.get('down', False)
        down_left = neighbors.get('down_left', False)
        down_right = neighbors.get('down_right', False)
    
        # Build a 16x24 tile (top segments + bottom segments)
        tile_surface = pygame.Surface((16, 24), pygame.SRCALPHA).convert_alpha()
        tile_surface.fill((0, 0, 0, 0))
    
        try:
            # Helper function to get segment with proper scaling
            def get_scaled_segment(rect_coords, target_width, target_height):
                segment = sprite.subsurface(pygame.Rect(*rect_coords))
                if segment.get_size() != (target_width, target_height):
                    return pygame.transform.scale(segment, (target_width, target_height))
                return segment
    
            # Top-left quadrant
            if not left and not up:
                # Corner piece - usually 8x16
                tl_rect = (0, 0, 8, 16)
                target_height = 16
            elif not up:
                # Top edge piece - usually 8x16  
                tl_rect = (16, 0, 8, 16)
                target_height = 16
            elif not left:
                # Left edge piece when neighbor above - usually 8x8
                tl_rect = (48, 8, 8, 8)
                target_height = 8  # FIXED: Don't stretch 8x8 to 8x16
            else:
                # Interior piece when neighbor above - usually 8x8
                tl_rect = (32, 8, 8, 8)
                target_height = 8  # FIXED: Don't stretch 8x8 to 8x16
            
            tl_segment = get_scaled_segment(tl_rect, 8, target_height)
            tile_surface.blit(tl_segment, (0, 0))
    
            # Top-right quadrant
            if not right and not up:
                # Corner piece - usually 8x16
                tr_rect = (8, 0, 8, 16)
                target_height = 16
            elif not up:
                # Top edge piece - usually 8x16
                tr_rect = (24, 0, 8, 16)
                target_height = 16
            elif not right:
                # Right edge piece when neighbor above - usually 8x8
                tr_rect = (56, 8, 8, 8)
                target_height = 8  # FIXED: Don't stretch 8x8 to 8x16
            else:
                # Interior piece when neighbor above - usually 8x8
                tr_rect = (40, 8, 8, 8)
                target_height = 8  # FIXED: Don't stretch 8x8 to 8x16
            
            tr_segment = get_scaled_segment(tr_rect, 8, target_height)
            tile_surface.blit(tr_segment, (8, 0))
    
            # Calculate where bottom segments should start
            # If top segments are 8px tall, bottom starts at y=8
            # If top segments are 16px tall, bottom starts at y=16
            bottom_y_start = 16 if target_height == 16 else 8
    
            # Bottom-left quadrant (always 8x8, positioned appropriately)
            if not left and not down:
                bl_rect = (0, 16, 8, 8)
            elif not down:
                bl_rect = (16, 16, 8, 8)
            elif left:
                bl_rect = (32, 16, 8, 8)
            elif not down_left:
                bl_rect = (48, 16, 8, 8)
            else:
                bl_rect = (32, 0, 8, 8)
            
            bl_segment = get_scaled_segment(bl_rect, 8, 8)
            tile_surface.blit(bl_segment, (0, bottom_y_start))
    
            # Bottom-right quadrant (always 8x8, positioned appropriately)
            if not right and not down:
                br_rect = (8, 16, 8, 8)
            elif not down:
                br_rect = (24, 16, 8, 8)
            elif right:
                br_rect = (40, 16, 8, 8)
            elif not down_right:
                br_rect = (56, 16, 8, 8)
            else:
                br_rect = (40, 0, 8, 8)
            
            br_segment = get_scaled_segment(br_rect, 8, 8)
            tile_surface.blit(br_segment, (8, bottom_y_start))
    
            # Calculate final tile height based on actual content
            # If we have tall top segments (16px) + bottom segments (8px) = 24px total
            # If we have short top segments (8px) + bottom segments (8px) = 16px total
            final_tile_height = bottom_y_start + 8
            
            # Scale the final tile to match current zoom level
            if size == 16 and final_tile_height == 16:
                # No scaling needed - direct blit
                surface.blit(tile_surface.subsurface((0, 0, 16, 16)), (screen_x, screen_y))
            else:
                # Scale proportionally
                final_width = size
                final_height = int(size * final_tile_height / 16)
                scaled_tile = pygame.transform.scale(
                    tile_surface.subsurface((0, 0, 16, final_tile_height)), 
                    (final_width, final_height)
                )
                
                # Position the scaled tile (align bottom with grid)
                adjusted_y = screen_y + size - final_height
                surface.blit(scaled_tile, (screen_x, adjusted_y))
    
        except Exception as e:
            print(f"Error in fixed smaller_blocks rendering: {e}")
            pygame.draw.rect(surface, (255, 0, 255), (screen_x, screen_y, size, size))
    
    def draw_platform_enhanced_sprite_optimized(self, surface, sprite, tile_info, screen_x, screen_y, size):
        """Optimized platform enhanced sprite drawing"""
        neighbors = tile_info.get('neighbors', {})
        left = neighbors.get('left', False)
        right = neighbors.get('right', False)
        is_odd_column = tile_info.get('is_odd_column', False)
        
        dx = 16 if is_odd_column else 0
        
        if left and right:
            sprite_rect = pygame.Rect(32 + dx, 0, 16, 16)
        elif left:
            sprite_rect = pygame.Rect(64, 0, 16, 16)
        elif right:
            sprite_rect = pygame.Rect(16, 0, 16, 16)
        else:
            sprite_rect = pygame.Rect(0, 0, 16, 16)
        
        try:
            if (sprite.get_width() >= sprite_rect.right and 
                sprite.get_height() >= sprite_rect.bottom):
                platform_slice = sprite.subsurface(sprite_rect)
                if size != 16:
                    scaled_slice = pygame.transform.scale(platform_slice, (size, size))
                    surface.blit(scaled_slice, (screen_x, screen_y))
                else:
                    surface.blit(platform_slice, (screen_x, screen_y))
            else:
                self.draw_standard_sprite_optimized(surface, sprite, screen_x, screen_y, size)
        except:
            self.draw_standard_sprite_optimized(surface, sprite, screen_x, screen_y, size)
    
    def draw_fence_enhanced_sprite_optimized(self, surface, sprite, tile_info, screen_x, screen_y, size):
        """Optimized fence enhanced sprite drawing"""
        neighbors = tile_info.get('neighbors', {})
        left = neighbors.get('left', False)
        right = neighbors.get('right', False)
        is_odd_column = tile_info.get('is_odd_column', False)
        
        dx = 16 if is_odd_column else 0
        
        if left and right:
            sprite_rect = pygame.Rect(48 + dx, 0, 16, sprite.get_height())
        elif left:
            sprite_rect = pygame.Rect(16, 0, 16, sprite.get_height())
        elif right:
            sprite_rect = pygame.Rect(0, 0, 16, sprite.get_height())
        else:
            sprite_rect = pygame.Rect(32, 0, 16, sprite.get_height())
        
        try:
            if (sprite.get_width() >= sprite_rect.right and 
                sprite.get_height() >= sprite_rect.bottom):
                fence_slice = sprite.subsurface(sprite_rect)
                
                sprite_height = fence_slice.get_height()
                if sprite_height > 16:
                    exact_tiles_tall = sprite_height / 16
                    scaled_height = int(exact_tiles_tall * size)
                    scaled_slice = pygame.transform.scale(fence_slice, (size, scaled_height))
                    adj_y = screen_y - size * (math.ceil(exact_tiles_tall) - 1)
                    surface.blit(scaled_slice, (screen_x, adj_y))
                else:
                    if size != 16:
                        scaled_slice = pygame.transform.scale(fence_slice, (size, size))
                        surface.blit(scaled_slice, (screen_x, screen_y))
                    else:
                        surface.blit(fence_slice, (screen_x, screen_y))
            else:
                self.draw_standard_sprite_optimized(surface, sprite, screen_x, screen_y, size)
        except:
            self.draw_standard_sprite_optimized(surface, sprite, screen_x, screen_y, size)
    
    def draw_bedrock_pattern_sprite_optimized(self, surface, sprite, tile_info, screen_x, screen_y, size):
        """Optimized bedrock pattern sprite drawing"""
        is_odd_column = tile_info.get('is_odd_column', False)
        is_odd_row = tile_info.get('is_odd_row', False)
        
        dx = 16 if is_odd_column else 0
        dy = 24 if is_odd_row else 0
        
        sprite_rect = pygame.Rect(0 + dx, 0 + dy, 16, 24)
        
        try:
            if (sprite.get_width() >= sprite_rect.right and 
                sprite.get_height() >= sprite_rect.bottom):
                pattern = sprite.subsurface(sprite_rect)
                
                scaled_width = size
                scaled_height = int(size * 1.5)
                
                scaled_pattern = pygame.transform.scale(pattern, (scaled_width, scaled_height))
                adj_screen_y = screen_y + size - scaled_height
                surface.blit(scaled_pattern, (screen_x, adj_screen_y))
            else:
                self.draw_standard_sprite_optimized(surface, sprite, screen_x, screen_y, size)
        except:
            self.draw_standard_sprite_optimized(surface, sprite, screen_x, screen_y, size)
    
    # Include ALL the remaining methods from the original tile_renderer.py
    def get_sprite_occupied_tiles(self, tile_x, tile_y, block_data, sprite=None):
        """Get list of all tiles occupied by a sprite at given position"""
        if sprite is None:
            sprite = self.block_manager.get_sprite(block_data.get('id', ''))
        
        tile_mode = block_data.get('tileMode', 'standard')
        bounds = self.calculate_sprite_bounds(sprite, tile_mode)
        
        occupied_tiles = []
        for dx, dy in bounds:
            occupied_tiles.append((tile_x + dx, tile_y + dy))
        
        return occupied_tiles
    
    def find_sprite_at_position(self, world_planner, target_x, target_y, layer):
        """Find if there's a sprite occupying the target position and return its origin"""
        layer_dict = world_planner.layers[layer]
        
        # Check all blocks in the layer
        for (origin_x, origin_y), block_data in layer_dict.items():
            sprite = self.block_manager.get_sprite(block_data.get('id', ''))
            occupied_tiles = self.get_sprite_occupied_tiles(origin_x, origin_y, block_data, sprite)
            
            # Check if target position is in occupied tiles
            if (target_x, target_y) in occupied_tiles:
                return (origin_x, origin_y), block_data
        
        return None, None
    
    def check_placement_collision(self, world_planner, tile_x, tile_y, block_data, layer):
        """Check if placing a sprite would collide with existing sprites on the same layer"""
        sprite = self.block_manager.get_sprite(block_data.get('id', ''))
        new_occupied_tiles = self.get_sprite_occupied_tiles(tile_x, tile_y, block_data, sprite)
        
        layer_dict = world_planner.layers[layer]
        
        # Check each tile the new sprite would occupy
        for occupied_x, occupied_y in new_occupied_tiles:
            # Check if this tile is already occupied by another sprite
            origin_pos, existing_block = self.find_sprite_at_position(world_planner, occupied_x, occupied_y, layer)
            if origin_pos is not None and origin_pos != (tile_x, tile_y):
                return True  # Collision detected
        
        return False  # No collision


# Keep the original RulesEngine class
class RulesEngine:
    """Handles tile connection rules and behaviors"""
    
    def __init__(self):
        self.rules = self.load_rules()
    
    def load_rules(self):
        """Load tile rules from JSON file"""
        try:
            with open('tile_rules.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print("tile_rules.json not found, using default rules")
            return self.get_default_rules()
        except Exception as e:
            print(f"Error loading tile_rules.json: {e}, using default rules")
            return self.get_default_rules()
    
    def get_default_rules(self):
        """Default tile rules configuration"""
        return {
            "tile_modes": {
                "vine": {
                    "type": "contextual_vertical",
                    "connects_to": ["vine", "solid"],
                    "sprite_layout": {
                        "single": {"x": 0, "y": 0, "width": 16, "height": 16},
                        "top": {"x": 16, "y": 0, "width": 16, "height": 16},
                        "middle": {"x": 0, "y": 16, "width": 16, "height": 16},
                        "bottom": {"x": 16, "y": 16, "width": 16, "height": 16}
                    }
                },
                "vertical": {
                    "type": "contextual_vertical",
                    "connects_to": ["vertical"],
                    "sprite_layout": {
                        "single": {"x": 0, "y": 0, "width": 16, "height": 24},
                        "top": {"x": 0, "y": 0, "width": 16, "height": 16},
                        "middle": {"x": 0, "y": 24, "width": 16, "height": 16},
                        "bottom": {"x": 0, "y": 16, "width": 16, "height": 8}
                    }
                },
                "standard": {
                    "type": "none",
                    "sprite_layout": {
                        "single": {"x": 0, "y": 0, "width": 16, "height": 16}
                    }
                }
            },
            "block_types": {
                "vine": "vine",
                "ivy": "vine",
                "glowingvines": "vine",
                "cactus": "vertical",
                "dirt": "standard",
                "stone": "standard",
                "wood": "standard"
            }
        }
    
    def get_tile_rules(self, block_id):
        """Get tile rules for a specific block ID"""
        block_type = self.get_block_type(block_id)
        mode_rules = self.rules["tile_modes"].get(block_type, self.rules["tile_modes"]["standard"])
        
        return {
            'tileSet': mode_rules["type"] != "none",
            'tileMode': block_type,
            'tileable': {
                'top': True,
                'right': True,
                'bottom': True,
                'left': True
            }
        }
    
    def get_block_type(self, block_id):
        """Determine block type from block ID"""
        block_id_lower = block_id.lower()
        
        if block_id_lower in self.rules["block_types"]:
            return self.rules["block_types"][block_id_lower]
        
        for pattern, block_type in self.rules["block_types"].items():
            if pattern in block_id_lower:
                return block_type
        
        return "standard"
