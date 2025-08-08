import os
import sys
import pygame
import pygame.freetype
from pygame.locals import *
from tkinter import Tk, filedialog
import math
import json

from constants import Tool, Layer, TileConnection, APP_VERSION
from tile_renderer import OptimizedTileRenderer  # Use optimized version
from block_manager import BlockManager
from chunk_manager import OptimizedChunkManager  # Use optimized version
from undo_manager import UndoRedoManager


class OptimizedBackgroundManager:
    """Optimized background manager with advanced caching and performance improvements"""
    
    def __init__(self):
        self.backgrounds = {}
        self.background_list = []
        self.current_background = None
        
        # Performance optimizations
        self.scaled_background_cache = {}
        self.last_cache_size = None
        self.cache_hits = 0
        self.cache_misses = 0
        
        self.load_backgrounds()
    
    def clear_background_cache(self):
        """Clear cached scaled backgrounds"""
        self.scaled_background_cache.clear()
        self.last_cache_size = None
        print(f"Background cache cleared. Stats - Hits: {self.cache_hits}, Misses: {self.cache_misses}")
        self.cache_hits = 0
        self.cache_misses = 0
    
    def get_background_directories(self):
        """Get directories containing background images"""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        dirs = []
        
        worldbgs_dir = os.path.join(base_dir, "worldbgs")
        if os.path.exists(worldbgs_dir):
            dirs.append(worldbgs_dir)
        
        bg_dir = os.path.join(base_dir, "backgrounds")
        if os.path.exists(bg_dir):
            dirs.append(bg_dir)
        
        return dirs
    
    def scan_directory_for_backgrounds(self, directory):
        """Recursively scan directory for background image files"""
        bg_files = []
        
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                    full_path = os.path.join(root, file)
                    bg_files.append(full_path)
        
        return bg_files
    
    def load_backgrounds(self):
        """Load all background images with optimization"""
        bg_dirs = self.get_background_directories()
        
        if not bg_dirs:
            print("Warning: No background directories found!")
            self.background_list.append({
                'id': 'none',
                'name': 'None',
                'surface': None,
                'path': None
            })
            self.current_background = 'none'
            return
        
        loaded_count = 0
        
        # Add "None" option first
        self.background_list.append({
            'id': 'none',
            'name': 'None',
            'surface': None,
            'path': None
        })
        
        for bg_dir in bg_dirs:
            print(f"Loading backgrounds from: {bg_dir}")
            bg_files = self.scan_directory_for_backgrounds(bg_dir)
            
            for bg_path in bg_files:
                if self.load_background_file(bg_path):
                    loaded_count += 1
        
        print(f"Loaded {loaded_count} background images")
        
        if len(self.background_list) > 1:
            self.current_background = self.background_list[1]['id']
        else:
            self.current_background = 'none'
    
    def load_background_file(self, bg_path):
        """Load a single background file with optimization"""
        try:
            filename = os.path.basename(bg_path)
            base_name = os.path.splitext(filename)[0]
            
            bg_name = base_name.replace('_', ' ').replace('-', ' ').title()
            
            bg_id = base_name.lower()
            original_id = bg_id
            counter = 1
            while bg_id in self.backgrounds:
                bg_id = f"{original_id}_{counter}"
                counter += 1
            
            # Load and immediately convert to display format for optimal performance
            bg_surface = pygame.image.load(bg_path)
            bg_surface = bg_surface.convert()  # Convert for faster blitting
            
            bg_info = {
                'id': bg_id,
                'name': bg_name,
                'surface': bg_surface,
                'path': bg_path
            }
            
            self.backgrounds[bg_id] = bg_info
            self.background_list.append(bg_info)
            
            print(f"Loaded background: {bg_name} from {bg_path}")
            return True
            
        except Exception as e:
            print(f"Error loading background {bg_path}: {e}")
            return False
    
    def get_current_background_cached(self, target_size=None):
        """Get current background with advanced caching for scaled versions"""
        if not self.current_background or self.current_background not in self.backgrounds:
            return None
        
        bg_surface = self.backgrounds[self.current_background]['surface']
        
        if target_size is None:
            return bg_surface
        
        # Use cache for scaled backgrounds
        cache_key = (self.current_background, target_size)
        
        if cache_key in self.scaled_background_cache:
            self.cache_hits += 1
            return self.scaled_background_cache[cache_key]
        
        self.cache_misses += 1
        
        # Create scaled version with optimal scaling
        try:
            if target_size == (bg_surface.get_width(), bg_surface.get_height()):
                scaled_bg = bg_surface
            else:
                # Use smoothscale for better quality
                scaled_bg = pygame.transform.smoothscale(bg_surface, target_size)
                scaled_bg = scaled_bg.convert()  # Convert for faster blitting
        except:
            scaled_bg = pygame.transform.scale(bg_surface, target_size)
            scaled_bg = scaled_bg.convert()
        
        # Cache management - keep cache size reasonable
        if len(self.scaled_background_cache) > 15:
            # Remove oldest entries (FIFO)
            oldest_keys = list(self.scaled_background_cache.keys())[:5]
            for key in oldest_keys:
                del self.scaled_background_cache[key]
        
        self.scaled_background_cache[cache_key] = scaled_bg
        return scaled_bg
    
    def get_current_background(self):
        """Get the current background surface"""
        return self.get_current_background_cached()
    
    def get_background_list(self):
        """Get list of all available backgrounds"""
        return self.background_list
    
    def set_current_background(self, bg_id):
        """Set the current background by ID"""
        if bg_id == 'none' or bg_id in self.backgrounds:
            if self.current_background != bg_id:
                self.current_background = bg_id
                self.clear_background_cache()  # Clear cache when background changes
                print(f"Background changed to: {bg_id}")
            return True
        return False
    
    def get_current_background_name(self):
        """Get the name of the current background"""
        if self.current_background == 'none':
            return "None"
        elif self.current_background and self.current_background in self.backgrounds:
            return self.backgrounds[self.current_background]['name']
        return "Unknown"

class UpdateManager:
    """Lightweight auto-update system using GitHub releases"""
    
    def __init__(self, current_version):
        self.current_version = str(current_version).strip()
        self.github_api_url = "https://api.github.com/repos/SavageTheUnicorn/CrystalRealmsWorldPlanner/releases/latest"
        self.update_available = False
        self.latest_version = None
        self.download_url = None
        self.check_complete = False
        
    def check_for_updates(self):
        """Check GitHub API for updates - non-blocking"""
        try:
            import threading
            # Use daemon=False for executables
            thread = threading.Thread(target=self._check_updates_thread, daemon=False)
            thread.start()
        except Exception as e:
            print(f"Failed to start update check thread: {e}")
            self.check_complete = True
    
    def _check_updates_thread(self):
        """Background thread to check for updates"""
        try:
            import urllib.request
            import json
            import ssl
            
            # Create SSL context that works in executable
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            request = urllib.request.Request(
                self.github_api_url,
                headers={'User-Agent': 'WorldPlanner-UpdateChecker/1.0'}
            )
            
            with urllib.request.urlopen(request, timeout=10, context=ssl_context) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    self.latest_version = data.get('tag_name', '').lstrip('v')
                    
                    if self._is_newer_version(self.latest_version):
                        # Find Windows executable in assets
                        for asset in data.get('assets', []):
                            if asset['name'].lower().endswith('.exe'):
                                self.download_url = asset['browser_download_url']
                                self.update_available = True
                                print(f"✅ Update available: {self.latest_version}")
                                break
                    else:
                        print(f"✅ Up to date: {self.current_version}")
        except Exception as e:
            print(f"Update check failed (this is normal): {e}")
        finally:
            self.check_complete = True
    
    def _is_newer_version(self, remote_version):
        """Compare version strings (simple semantic versioning)"""
        try:
            if not remote_version or not self.current_version:
                return False
                
            current_parts = [int(x) for x in self.current_version.split('.')]
            remote_parts = [int(x) for x in remote_version.split('.')]
            
            # Pad shorter version with zeros
            max_len = max(len(current_parts), len(remote_parts))
            current_parts += [0] * (max_len - len(current_parts))
            remote_parts += [0] * (max_len - len(remote_parts))
            
            return remote_parts > current_parts
        except Exception as e:
            print(f"Version comparison failed: {e}")
            return False
    
    def download_and_install_update(self):
        """Download and install update"""
        if not self.update_available or not self.download_url:
            return False
        
        try:
            import urllib.request
            import os
            import subprocess
            import sys
            import ssl
            
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            print(f"Downloading update {self.latest_version}...")
            
            # Get the actual name of the current executable
            if getattr(sys, 'frozen', False):
                # Running as PyInstaller executable
                current_exe_path = sys.argv[0]
                current_exe_name = os.path.basename(current_exe_path)
            else:
                # Running from source (fallback)
                current_exe_name = "WorldPlanner.exe"
            
            print(f"Current executable name: {current_exe_name}")
            
            request = urllib.request.Request(
                self.download_url,
                headers={'User-Agent': 'WorldPlanner-UpdateChecker/1.0'}
            )
            
            with urllib.request.urlopen(request, context=ssl_context) as response:
                with open("WorldPlanner_new.exe", 'wb') as f:
                    f.write(response.read())
            
            # Dynamic batch script using the actual executable name
            batch_script = f"""@echo off
            echo Updating {current_exe_name}...
            
            REM Kill any remaining processes with this name
            taskkill /f /im "{current_exe_name}" >nul 2>&1
            
            REM Remove old version
            if exist "{current_exe_name}" del "{current_exe_name}"
            
            REM Install new version with the correct name
            if exist WorldPlanner_new.exe ren WorldPlanner_new.exe "{current_exe_name}"
            
            REM Start new version with full path
            timeout /t 1 /nobreak >nul
            if exist "{current_exe_name}" (
                echo Starting {current_exe_name}...
                start "" "%~dp0{current_exe_name}"
            )
            
            REM Clean up
            del "%~f0"
            """
            
            with open("update.bat", "w") as f:
                f.write(batch_script)
            
            print(f"Starting update process for {current_exe_name}...")
            
            # Start batch file with no window
            subprocess.Popen(
                ["cmd", "/c", "update.bat"], 
                creationflags=subprocess.CREATE_NO_WINDOW,
                cwd=os.getcwd()
            )
            
            # Exit the application immediately
            import pygame
            pygame.event.post(pygame.event.Event(pygame.QUIT))
            
            return True
            
        except Exception as e:
            print(f"Update installation failed: {e}")
            return False

class OptimizedTooltipManager:
    """Optimized tooltip manager with surface caching and batch rendering"""
    
    def __init__(self, font):
        self.font = font
        self.current_tooltip = None
        self.tooltip_timer = 0
        self.tooltip_delay = 300
        self.tooltip_surface = None
        self.tooltip_rect = None
        
        # Advanced caching system
        self.surface_cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Pre-rendered common tooltips
        self.prerender_common_tooltips()
        
    def prerender_common_tooltips(self):
        """Pre-render commonly used tooltips"""
        common_tooltips = [
            "Toggle grid display (G)",
            "Toggle block borders", 
            "Save world to file",
            "Load world from file",
            "Export world as image",
            "Clear entire world",
            "Upload custom sprite files",
            "Search blocks (Ctrl+F)",
            "Undo last action (Ctrl+Z)",
            "Redo last undone action (Ctrl+Y)",
            "Previous background",
            "Next background",
            "No background"
        ]
        
        for tooltip_text in common_tooltips:
            self.create_tooltip_surface_cached(tooltip_text, (0, 0), prerender_only=True)
    
    def set_tooltip(self, text, mouse_pos):
        """Set tooltip text and position with advanced caching"""
        if self.current_tooltip != text:
            self.current_tooltip = text
            self.tooltip_timer = pygame.time.get_ticks()
            self.tooltip_surface = None
            
        if text and self.tooltip_surface is None:
            if pygame.time.get_ticks() - self.tooltip_timer > self.tooltip_delay:
                self.create_tooltip_surface_cached(text, mouse_pos)
    
    def create_tooltip_surface_cached(self, text, mouse_pos, prerender_only=False):
        """Create tooltip surface with advanced caching system"""
        if not text:
            return
        
        # Check cache first
        if text in self.surface_cache:
            self.tooltip_surface = self.surface_cache[text]
            self.cache_hits += 1
        else:
            self.cache_misses += 1
            
            # Create new tooltip surface with optimized rendering
            text_surface, text_rect = self.font.render(text, (255, 255, 255))
            padding = 8
            
            tooltip_width = text_rect.width + padding * 2
            tooltip_height = text_rect.height + padding * 2
            
            # Create surface with optimal format
            surface = pygame.Surface((tooltip_width, tooltip_height), pygame.SRCALPHA)
            surface = surface.convert_alpha()  # Convert for faster blitting
            
            # Use batch drawing for efficiency
            pygame.draw.rect(surface, (80, 80, 30, 240), 
                            (0, 0, tooltip_width, tooltip_height))
            pygame.draw.rect(surface, (255, 255, 150), 
                            (0, 0, tooltip_width, tooltip_height), 2)
            
            surface.blit(text_surface, (padding, padding))
            
            # Cache management - limit cache size but keep frequently used tooltips
            if len(self.surface_cache) > 100:
                # Remove less common tooltips (keep first 50 which are likely common ones)
                cache_items = list(self.surface_cache.items())
                for key, _ in cache_items[50:]:
                    del self.surface_cache[key]
            
            self.surface_cache[text] = surface
            self.tooltip_surface = surface
        
        if prerender_only:
            return
        
        # Position tooltip optimally - FIXED positioning
        if self.tooltip_surface:
            tooltip_width = self.tooltip_surface.get_width()
            tooltip_height = self.tooltip_surface.get_height()
            
            # Position tooltip slightly above and centered on mouse
            tooltip_x = mouse_pos[0] - tooltip_width // 2
            tooltip_y = mouse_pos[1] - tooltip_height - 30  # 10px above mouse
            
            # Keep tooltip on screen (boundary checking)
            tooltip_x = max(10, min(tooltip_x, pygame.display.get_surface().get_width() - tooltip_width - 10))
            tooltip_y = max(10, tooltip_y)  # Don't go above screen top
            
            # If tooltip would go above screen, show it below mouse instead
            if tooltip_y < 10:
                tooltip_y = mouse_pos[1] + 20  # 20px below mouse
            
            self.tooltip_rect = pygame.Rect(tooltip_x, tooltip_y, tooltip_width, tooltip_height)
    
    def clear_tooltip(self):
        """Clear current tooltip"""
        self.current_tooltip = None
        self.tooltip_surface = None
        self.tooltip_rect = None
        
    def draw(self, surface, screen_width, screen_height):
        """Draw tooltip with optimized positioning"""
        if self.tooltip_surface and self.tooltip_rect:
            # Optimized boundary checking
            if self.tooltip_rect.right > screen_width:
                self.tooltip_rect.x = screen_width - self.tooltip_rect.width - 10
            if self.tooltip_rect.left < 10:
                self.tooltip_rect.x = 10
                
            surface.blit(self.tooltip_surface, self.tooltip_rect)
    
    def get_cache_stats(self):
        """Get cache performance statistics"""
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total * 100) if total > 0 else 0
        return f"Tooltip Cache: {hit_rate:.1f}% hit rate ({self.cache_hits}/{total})"


class OptimizedHotkeyHelpManager:
    """Optimized hotkey help manager with surface caching and dirty flagging"""
    
    def __init__(self, font, font_small):
        self.font = font
        self.font_small = font_small
        self.visible = True
        self.surface = None
        self.position = None
        self.surface_dirty = True
        
        # Performance optimizations
        self.last_render_time = 0
        self.render_throttle = 100  # Only re-render every 100ms if needed
        
        self.update_help()
    
    def get_current_hotkeys(self):
        """Get current contextual hotkeys - optimized structure"""
        return [
            [
                ("Tools:", ""),
                ("P", "Place"),
                ("B", "Brush"),
                ("F", "Fill"),
                ("E", "Erase"),
                ("S", "Select"),
                ("V", "Paste"),
                ("I", "Eyedropper")
            ],
            [
                ("Layers:", ""),
                ("1", "Background"),
                ("2", "Foreground"),
                ("", ""),
                ("General:", ""),
                ("Ctrl+Z", "Undo"),
                ("Ctrl+Y", "Redo"),
                ("F1", "Hide Tooltips"),
                ("F2", "Debug Sprite")
            ],
            [
                ("View:", ""),
                ("G", "Toggle Grid"),
                ("Ctrl+F", "Search"),
                ("Esc", "Cancel/Exit"),
                ("", ""),
                ("Camera:", ""),
                ("Right Click", " Pan"),
                ("Ctrl+Scroll", " Zoom"),
                ("Shift+Scroll", " Pan-H")
            ]
        ]
    
    def update_help(self):
        """Update the help surface - only if dirty and throttled"""
        current_time = pygame.time.get_ticks()
        
        if (not self.surface_dirty or 
            current_time - self.last_render_time < self.render_throttle):
            return
            
        columns = self.get_current_hotkeys()
        
        # Pre-calculate dimensions
        line_height = 14
        column_width = 140
        padding = 8
        column_gap = 20
        
        total_width = len(columns) * column_width + (len(columns) - 1) * column_gap + padding * 2
        max_height = max(len(col) for col in columns) * line_height + padding * 2
        
        # Create surface with optimal format
        self.surface = pygame.Surface((total_width, max_height), pygame.SRCALPHA)
        self.surface = self.surface.convert_alpha()  # Convert for faster blitting
        
        # Batch background drawing
        pygame.draw.rect(self.surface, (80, 80, 80, 240), (0, 0, total_width, max_height))
        pygame.draw.rect(self.surface, (150, 150, 150, 120), (0, 0, total_width, max_height), 2)
        
        # Optimized text rendering - batch by color
        white_texts = []
        light_gray_texts = []
        
        for col_idx, column in enumerate(columns):
            x_start = padding + col_idx * (column_width + column_gap)
            y = padding
            
            for key, desc in column:
                if key == "" and desc == "":
                    y += line_height // 2
                    continue
                    
                if desc == "":
                    if key:
                        light_gray_texts.append((key, (x_start, y)))
                else:
                    if key:
                        key_surface, key_rect = self.font_small.render(key, (200, 200, 200))
                        key_width = key_rect.width
                        light_gray_texts.append((key, (x_start, y)))
                        if desc:
                            white_texts.append((desc, (x_start + key_width + 5, y)))
                
                y += line_height
        
        # Render texts in batches by color for efficiency
        for text, pos in light_gray_texts:
            text_surface, _ = self.font_small.render(text, (200, 200, 200))
            self.surface.blit(text_surface, pos)
            
        for text, pos in white_texts:
            text_surface, _ = self.font_small.render(text, (220, 220, 220))
            self.surface.blit(text_surface, pos)
        
        self.surface_dirty = False
        self.last_render_time = current_time
    
    def toggle_visibility(self):
        """Toggle help visibility"""
        self.visible = not self.visible
    
    def mark_dirty(self):
        """Mark surface as needing re-render"""
        self.surface_dirty = True
    
    def draw(self, surface, screen_width, toolbar_width, resize_handle_width):
        """Draw hotkey help with optimized positioning"""
        if not self.visible or not self.surface:
            return
            
        canvas_width = screen_width - toolbar_width - resize_handle_width
        x = toolbar_width + resize_handle_width + (canvas_width - self.surface.get_width()) // 2
        y = 10
        
        # Optimized boundary checking
        if x < toolbar_width + resize_handle_width:
            x = toolbar_width + resize_handle_width + 10
        elif x + self.surface.get_width() > screen_width:
            x = screen_width - self.surface.get_width() - 10
            
        surface.blit(self.surface, (x, y))

class OptimizedBrushManager:
    """High-performance brush manager with real-time visual feedback and optimized chunk updates"""
    
    def __init__(self, world_planner):
        self.world_planner = world_planner
        
        # Pre-calculated brush patterns (cached)
        self.brush_patterns = {}  # {(size, shape): [(dx, dy), ...]}
        
        # Spatial index for fast collision detection
        self.spatial_index = {}  # {(x, y): (origin_x, origin_y)}
        self.index_dirty = True
        
        # Batch operation state
        self.active_stroke = False
        self.stroke_positions = set()
        self.stroke_timer = 0
        self.stroke_batch_delay = 50  # ms
        
        # Performance tracking
        self.last_brush_pos = None
        
    def get_brush_pattern(self, size, shape):
        """Get pre-calculated brush pattern"""
        key = (size, shape)
        if key not in self.brush_patterns:
            pattern = []
            radius = size - 1
            
            if shape == 'square':
                for dy in range(-radius, radius + 1):
                    for dx in range(-radius, radius + 1):
                        pattern.append((dx, dy))
            else:  # circle
                for dy in range(-radius, radius + 1):
                    for dx in range(-radius, radius + 1):
                        if dx*dx + dy*dy <= radius*radius:
                            pattern.append((dx, dy))
            
            self.brush_patterns[key] = pattern
        
        return self.brush_patterns[key]
    
    def update_spatial_index(self):
        """Update spatial index for fast collision detection"""
        if not self.index_dirty:
            return
            
        self.spatial_index.clear()
        
        # Index all sprites by their occupied tiles
        for layer_enum in [self.world_planner.active_layer]:  # Only index active layer
            layer = self.world_planner.layers[layer_enum]
            for (origin_x, origin_y), block_data in layer.items():
                sprite = self.world_planner.block_manager.get_sprite(block_data.get('id', ''))
                occupied_tiles = self.world_planner.tile_renderer.get_sprite_occupied_tiles(
                    origin_x, origin_y, block_data, sprite
                )
                for tile_x, tile_y in occupied_tiles:
                    self.spatial_index[(tile_x, tile_y)] = (origin_x, origin_y)
        
        self.index_dirty = False
    
    def fast_collision_check(self, tile_x, tile_y):
        """Fast collision check using spatial index"""
        self.update_spatial_index()
        return (tile_x, tile_y) in self.spatial_index
    
    def fast_find_sprite_at_position(self, tile_x, tile_y):
        """Fast sprite lookup using spatial index"""
        self.update_spatial_index()
        origin_pos = self.spatial_index.get((tile_x, tile_y))
        if origin_pos:
            layer = self.world_planner.layers[self.world_planner.active_layer]
            block_data = layer.get(origin_pos)
            return origin_pos, block_data
        return None, None
    
    def start_brush_stroke(self):
        """Start a new brush stroke"""
        self.active_stroke = True
        self.stroke_positions.clear()
        self.stroke_timer = pygame.time.get_ticks()
    
    def add_brush_position(self, center_x, center_y, is_erase=False):
        """OPTIMIZED: Pre-calculated bounds with proper sprite origin alignment and brush replacement"""
        if not self.active_stroke:
            self.start_brush_stroke()
        
        # INTERPOLATION FIX: Fill gaps between mouse positions
        current_pos = (center_x, center_y)
        positions_to_process = [current_pos]
        
        if self.last_brush_pos and self.last_brush_pos != current_pos:
            positions_to_process = self.interpolate_brush_positions(self.last_brush_pos, current_pos)
        
        self.last_brush_pos = current_pos
        
        # Get brush pattern (cached)
        pattern = self.get_brush_pattern(self.world_planner.brush_size, self.world_planner.brush_shape)
        layer_dict = self.world_planner.layers[self.world_planner.active_layer]
        
        # PRE-CALCULATE sprite bounds once for the entire brush operation
        sprite_bounds = None
        grid_width, grid_height = 1, 1
        
        if not is_erase and self.world_planner.selected_block:
            block_data = self.world_planner.create_block_data_from_selected()
            if block_data:
                sprite = self.world_planner.block_manager.get_sprite(block_data.get('id', ''))
                if sprite:
                    tile_mode = block_data.get('tileMode', 'standard')
                    sprite_bounds = self.world_planner.tile_renderer.calculate_sprite_bounds(sprite, tile_mode)
                    
                    # Calculate grid size for proper alignment
                    if sprite_bounds:
                        min_x = min(dx for dx, dy in sprite_bounds)
                        max_x = max(dx for dx, dy in sprite_bounds)
                        min_y = min(dy for dx, dy in sprite_bounds)
                        max_y = max(dy for dx, dy in sprite_bounds)
                        grid_width = max_x - min_x + 1
                        grid_height = max_y - min_y + 1
        
        # Track new positions for efficient chunk updates
        new_positions_this_batch = []
        
        # Process all interpolated positions with optimized collision detection
        for brush_center_x, brush_center_y in positions_to_process:
            for dx, dy in pattern:
                tile_x, tile_y = brush_center_x + dx, brush_center_y + dy
                
                if not self.world_planner.is_valid_position(tile_x, tile_y):
                    continue
                
                if is_erase:
                    # FIXED: Check for bedrock before erasing
                    if self.world_planner.is_bedrock_position(tile_y):
                        continue
                        
                    # Simple erase - just remove if exists (but not bedrock)
                    pos = (tile_x, tile_y)
                    if pos in layer_dict:
                        del layer_dict[pos]
                        self.stroke_positions.add(pos)
                        new_positions_this_batch.append(pos)
                else:
                    # OPTIMIZED PLACEMENT with brush replacement behavior
                    if sprite_bounds and len(sprite_bounds) > 1:
                        # Multi-tile sprite - calculate proper origin for bottom alignment
                        sprite_origin_x, sprite_origin_y = self.calculate_sprite_origin(tile_x, tile_y, sprite_bounds)
                        
                        # Align to grid using the calculated origin
                        aligned_x, aligned_y = self.align_to_sprite_grid(sprite_origin_x, sprite_origin_y, grid_width, grid_height)
                        
                        # Move collision check position down by 1 tile to match preview
                        collision_check_y = aligned_y + 1
                        
                        # Check basic validity (world bounds and bedrock only)
                        can_place = True
                        for bound_dx, bound_dy in sprite_bounds:
                            check_pos = (aligned_x + bound_dx, collision_check_y + bound_dy)
                            if (not self.world_planner.is_valid_position(check_pos[0], check_pos[1]) or
                                self.world_planner.is_bedrock_position(check_pos[1])):
                                can_place = False
                                break
                        
                        if can_place:
                            # Remove any existing sprites that would be overlapped (brush replacement)
                            sprites_to_remove = set()
                            for bound_dx, bound_dy in sprite_bounds:
                                check_pos = (aligned_x + bound_dx, collision_check_y + bound_dy)
                                origin_pos, _ = self.fast_find_sprite_at_position(check_pos[0], check_pos[1])
                                if origin_pos:
                                    sprites_to_remove.add(origin_pos)
                            
                            # Remove existing sprites
                            for origin_pos in sprites_to_remove:
                                if origin_pos in layer_dict:
                                    del layer_dict[origin_pos]
                            
                            block_data = self.world_planner.create_block_data_from_selected()
                            if block_data:
                                # FIXED: Move actual sprite placement down by 2 tiles total to fix rendering position
                                actual_placement_y = aligned_y + 1
                                layer_dict[(aligned_x, actual_placement_y)] = block_data.copy()
                                self.stroke_positions.add((aligned_x, actual_placement_y))
                                new_positions_this_batch.append((aligned_x, actual_placement_y))
                    else:
                        # Single tile sprite - simple placement with replacement
                        pos = (tile_x, tile_y)
                        if not self.world_planner.is_bedrock_position(tile_y):
                            block_data = self.world_planner.create_block_data_from_selected()
                            if block_data:
                                # Remove existing sprite if any (brush replacement behavior)
                                if pos in layer_dict:
                                    del layer_dict[pos]
                                layer_dict[pos] = block_data.copy()
                                self.stroke_positions.add(pos)
                                new_positions_this_batch.append(pos)
        
        # Simple tracking for final update
        if new_positions_this_batch:
            self.immediate_visual_update(new_positions_this_batch)

    def interpolate_brush_positions(self, start_pos, end_pos):
        """Fill gaps between mouse positions for smooth brush strokes"""
        start_x, start_y = start_pos
        end_x, end_y = end_pos
        
        # Calculate distance and steps needed
        dx = end_x - start_x
        dy = end_y - start_y
        distance = max(abs(dx), abs(dy))
        
        if distance <= 1:
            return [end_pos]
        
        # Generate interpolated positions
        positions = []
        for i in range(distance + 1):
            t = i / distance
            interp_x = int(start_x + dx * t)
            interp_y = int(start_y + dy * t)
            positions.append((interp_x, interp_y))
        
        return positions

    def calculate_sprite_origin(self, click_x, click_y, sprite_bounds):
        """Calculate proper sprite origin for bottom-aligned placement"""
        if not sprite_bounds:
            return click_x, click_y
        
        # Find the bottom-most tile of the sprite
        min_y = min(dy for dx, dy in sprite_bounds)
        
        # FIXED: Adjust origin so bottom of sprite aligns with clicked position
        # Move down by 1 tile to fix the "1 tile too high" issue
        origin_x = click_x
        origin_y = click_y - min_y - 1  # Added +1 to move sprites down by 1 tile
        
        return origin_x, origin_y

    def align_to_sprite_grid(self, tile_x, tile_y, grid_width, grid_height):
        """Align sprite placement to grid boundaries with bottom-alignment for tall sprites"""
        # Calculate grid origin
        grid_origin_x = 0
        grid_origin_y = 0
        
        # Snap to grid
        aligned_x = ((tile_x - grid_origin_x) // grid_width) * grid_width + grid_origin_x
        aligned_y = ((tile_y - grid_origin_y) // grid_height) * grid_height + grid_origin_y
        
        return aligned_x, aligned_y

    def fast_multi_tile_collision_check(self, origin_x, origin_y, sprite_bounds, layer_dict):
        """Fast collision check using pre-calculated sprite bounds"""
        # Check if any tile in the sprite footprint is occupied
        for dx, dy in sprite_bounds:
            check_pos = (origin_x + dx, origin_y + dy)
            
            # Basic world bounds check
            if not self.world_planner.is_valid_position(check_pos[0], check_pos[1]):
                return False
            if self.world_planner.is_bedrock_position(check_pos[1]):
                return False
                
            # Simple occupancy check
            if check_pos in layer_dict:
                return False
        
        return True

    def get_brush_collision_preview(self, center_x, center_y):
        """Fast collision preview for brush with proper sprite origin"""
        if not self.world_planner.selected_block:
            return {}
        
        pattern = self.get_brush_pattern(self.world_planner.brush_size, self.world_planner.brush_shape)
        layer_dict = self.world_planner.layers[self.world_planner.active_layer]
        
        # Pre-calculate sprite info once
        block_data = self.world_planner.create_block_data_from_selected()
        if not block_data:
            return {}
        
        sprite = self.world_planner.block_manager.get_sprite(block_data.get('id', ''))
        sprite_bounds = [(0, 0)]  # Default single tile
        grid_width, grid_height = 1, 1
        
        if sprite:
            tile_mode = block_data.get('tileMode', 'standard')
            sprite_bounds = self.world_planner.tile_renderer.calculate_sprite_bounds(sprite, tile_mode)
            
            if sprite_bounds and len(sprite_bounds) > 1:
                min_x = min(dx for dx, dy in sprite_bounds)
                max_x = max(dx for dx, dy in sprite_bounds)
                min_y = min(dy for dx, dy in sprite_bounds)
                max_y = max(dy for dx, dy in sprite_bounds)
                grid_width = max_x - min_x + 1
                grid_height = max_y - min_y + 1
        
        # Calculate collision state for each brush position
        collision_info = {}
        
        for dx, dy in pattern:
            tile_x, tile_y = center_x + dx, center_y + dy
            
            if not self.world_planner.is_valid_position(tile_x, tile_y):
                continue
            
            if len(sprite_bounds) > 1:
                # Multi-tile sprite with proper origin calculation
                sprite_origin_x, sprite_origin_y = self.calculate_sprite_origin(tile_x, tile_y, sprite_bounds)
                aligned_x, aligned_y = self.align_to_sprite_grid(sprite_origin_x, sprite_origin_y, grid_width, grid_height)
                
                # FIXED: Move preview down by 1 tile for visual alignment
                preview_aligned_y = aligned_y + 1
                
                # Use the SAME position for collision check as actual placement
                has_collision = not self.fast_multi_tile_collision_check(aligned_x, preview_aligned_y, sprite_bounds, layer_dict)
                collision_info[(tile_x, tile_y)] = {
                    'has_collision': has_collision,
                    'aligned_pos': (aligned_x, preview_aligned_y),  # Use preview_aligned_y for visual
                    'sprite_bounds': sprite_bounds
                }
            else:
                # Single tile sprite
                has_collision = ((tile_x, tile_y) in layer_dict or 
                            self.world_planner.is_bedrock_position(tile_y))
                collision_info[(tile_x, tile_y)] = {
                    'has_collision': has_collision,
                    'aligned_pos': (tile_x, tile_y),
                    'sprite_bounds': sprite_bounds
                }
        
        return collision_info

    def immediate_visual_update(self, new_positions):
        """Simplified: Just track positions for final update"""
        if not hasattr(self, 'pending_updates'):
            self.pending_updates = []
        
        self.pending_updates.extend(new_positions)
    
    def should_update_chunks(self):
        """Check if enough time has passed to update chunks"""
        return pygame.time.get_ticks() - self.stroke_timer > self.stroke_batch_delay
    
    def finish_brush_stroke(self, force=False):
        """Finish current brush stroke with final optimization pass"""
        if not self.active_stroke:
            return
            
        # Process any remaining pending updates
        if hasattr(self, 'pending_updates') and self.pending_updates:
            self.pending_updates.clear()
        
        # Reset stroke state
        self.active_stroke = False
        self.last_brush_pos = None
        stroke_positions = list(self.stroke_positions)
        self.stroke_positions.clear()
        
        # Clean up batch tracking
        if hasattr(self, 'pending_updates'):
            delattr(self, 'pending_updates')
        
        # FIXED: Always mark spatial index dirty when stroke ends
        self.index_dirty = True
        
        # FIXED: Force chunk update for ALL stroke positions, not just first 50
        if stroke_positions:
            # Force immediate chunk updates for all affected positions
            self.world_planner.chunk_manager.force_update_affected_chunks(stroke_positions)
            
            # FIXED: Force immediate visual refresh for erase operations
            self.world_planner.force_immediate_chunk_update()
            
            # FIXED: Additional invalidation for erase operations to ensure visual update
            if force:
                # Get all affected chunks and force them to re-render
                affected_chunks = set()
                for pos in stroke_positions:
                    chunk_key = self.world_planner.chunk_manager.get_chunk_key(pos[0], pos[1])
                    affected_chunks.add(chunk_key)
                
                # Force each affected chunk to completely re-render
                for chunk_key in affected_chunks:
                    if chunk_key in self.world_planner.chunk_manager.chunks:
                        chunk = self.world_planner.chunk_manager.chunks[chunk_key]
                        chunk.dirty = True
                        chunk.blocks_hash = None
                        chunk.last_zoom = None
                        chunk.surface = None  # Force surface recreation
    
    def invalidate_spatial_index(self):
        """Mark spatial index as needing rebuild"""
        self.index_dirty = True

class OptimizedWorldPlanner:
    """Optimized World Planner with comprehensive performance improvements"""
    
    def __init__(self):
        from constants import Tool, Layer, TileConnection, APP_VERSION
        # Initialize pygame with optimization hints
        pygame.init()
        pygame.display.set_caption("Crystal Realms World Planner - made by SavageTheUnicorn")
        
        # Set optimization environment variables
        os.environ['SDL_VIDEO_CENTERED'] = '1'
        
        # Display setup with hardware acceleration attempts
        self.screen_width = 1280
        self.screen_height = 720
        
        # Try to enable hardware acceleration and optimal surface formats
        try:
            pygame.display.gl_set_attribute(pygame.GL_DOUBLEBUFFER, 1)
            self.screen = pygame.display.set_mode(
                (self.screen_width, self.screen_height), 
                pygame.RESIZABLE | pygame.HWSURFACE | pygame.DOUBLEBUF
            )
            print("✅ Hardware acceleration enabled")
        except:
            self.screen = pygame.display.set_mode(
                (self.screen_width, self.screen_height), 
                pygame.RESIZABLE
            )
            print("⚠️ Using software rendering")
        
        # Performance monitoring and adaptive settings
        self.performance_stats = {
            'chunks_rendered': 0,
            'frame_time': 0,
            'render_time': 0,
            'fps': 0,
            'adaptive_quality': 1.0
        }
        
        self.frame_skip_threshold = 50  # Skip rendering if frame time exceeds this
        self.adaptive_chunk_rendering = True
        self.last_frame_time = 0
        self.frame_count = 0
        self.performance_timer = pygame.time.get_ticks()
        
        # Initialize optimized components
        self.block_manager = BlockManager()
        self.tile_renderer = OptimizedTileRenderer(self.block_manager)
        
        # Initialize optimized background manager
        self.background_manager = OptimizedBackgroundManager()
        
        # Initialize undo/redo manager
        self.undo_manager = UndoRedoManager(max_history_size=500)
        
        # Set up fonts with optimization
        pygame.freetype.init()
        self.font = pygame.freetype.SysFont('Arial', 14)
        self.font_small = pygame.freetype.SysFont('Arial', 12)
        
        # Initialize optimized UI managers
        self.tooltip_manager = OptimizedTooltipManager(self.font)
        self.hotkey_help = OptimizedHotkeyHelpManager(self.font, self.font_small)
        
        # Grid and tile settings
        self.tile_size = 16
        self.zoom = 2
        self.camera_x = 0
        self.camera_y = 0
        
        # World size limits
        self.world_width = 301
        self.world_height = 171
        self.bedrock_rows = 6
        
        # Game state
        self.active_layer = Layer.MIDGROUND
        self.layers = {
            Layer.BACKGROUND: {},
            Layer.MIDGROUND: {}
        }
        self.active_tool = Tool.PLACE
        self.previous_tool = Tool.PLACE
        self.selected_block = None
        self.is_dragging = False
        self.last_mouse_pos = (0, 0)
        
        # Selection state
        self.selection = None
        self.selection_start = None
        self.clipboard = None
        
        # Brush settings
        self.brush_size = 1
        self.brush_shape = "square"
        
        # Custom brush size input
        self.is_inputting_brush_size = False
        self.custom_brush_text = ""
        self.custom_brush_cursor_pos = 0
        
        # Display settings
        self.show_borders = False
        self.show_grid = True
        
        # UI dimensions
        self.toolbar_width = 250
        self.min_toolbar_width = 180
        self.max_toolbar_width = 350
        self.toolbar_scroll_y = 0
        self.toolbar_max_scroll = 0
        self.resize_handle_width = 8
        self.is_resizing_toolbar = False
        
        # Scrollbar properties
        self.scrollbar_width = 12
        self.scrollbar_track_color = (60, 60, 60)
        self.scrollbar_thumb_color = (120, 120, 120)
        self.scrollbar_thumb_hover_color = (150, 150, 150)
        self.is_dragging_scrollbar = False
        self.scrollbar_drag_offset = 0
        
        self.canvas_rect = pygame.Rect(
            self.toolbar_width + self.resize_handle_width, 0,
            self.screen_width - self.toolbar_width - self.resize_handle_width,
            self.screen_height
        )
        
        # UI elements with caching
        self.buttons = {}
        self.toolbuttons = {}
        self.category_expanded = {}
        self.block_buttons = {}
        
        # UI surface caching
        self.ui_surface_cache = {}
        self.ui_cache_dirty = True
        
        # Recent blocks
        self.recent_blocks = []
        
        # Search functionality
        self.search_text = ""
        self.is_searching = False
        self.search_cursor_pos = 0
        
        # Autotiling settings
        self.auto_tile = True
        
        # Batch operation tracking
        self.batch_operation_active = False
        self.batch_operation_description = ""
        
        # Load sprites AFTER components are initialized
        try:
            self.block_manager.load_sprites()
        except Exception as e:
            print(f"Error loading sprites: {e}")
        
        # Set first block as selected
        terrain_blocks = self.block_manager.get_blocks_by_category('terrain')
        if terrain_blocks:
            self.selected_block = terrain_blocks[0]
        
        # Initialize UI
        self.init_ui()
        
        # Create bedrock
        self.place_bedrock()
        
        # Initialize optimized chunk manager AFTER layers are set up
        self.chunk_manager = OptimizedChunkManager(self, chunk_size=24)
        
        # Initialize optimized brush manager
        self.brush_manager = OptimizedBrushManager(self)
        
        # HOTFIX: Override the broken grid drawing method in chunk manager
        self.fix_chunk_grid_rendering()
        
        # Save initial state to undo manager
        self.undo_manager.save_state(self.layers, "Initial state")
        
        # Clock for limiting framerate with performance monitoring
        self.clock = pygame.time.Clock()
        self.running = True
        
        print("🚀 Optimized World Planner initialized successfully!")
        print(f"Pygame version: {pygame.version.ver}")
        print(f"SDL version: {pygame.version.SDL}")
        print(f"Display driver: {pygame.display.get_driver()}")
        
        # Camera optimization
        self.last_camera_update = 0
        self.camera_update_threshold = 16  # ~60fps throttling
        
        # Mouse coordinate tracking
        self.mouse_grid_x = 0
        self.mouse_grid_y = 0
        self.show_coordinates = True
        
        # Autosave system
        self.autosave_timer = 0
        self.autosave_interval = 60000  # 1 minute in milliseconds
        self.max_autosave_files = 30
        self.autosave_directory = "autosaves"
        self.ensure_autosave_directory()
        self.update_manager = None
        self.update_check_attempted = False
        self.last_update_state = False
        self.update_init_timer = pygame.time.get_ticks() + 3000
    
    def ensure_autosave_directory(self):
        """Ensure autosave directory exists"""
        try:
            if not os.path.exists(self.autosave_directory):
                os.makedirs(self.autosave_directory)
                print(f"Created autosave directory: {self.autosave_directory}")
        except Exception as e:
            print(f"Warning: Could not create autosave directory: {e}")
            self.autosave_directory = None  # Disable autosave if directory creation fails
    
    def place_bedrock(self):
        """Place bedrock sprites in bottom rows of the world"""
        # Find a bedrock sprite from the bedrockandwater directory
        bedrock_block = None
        
        # Look for bedrock sprites in custom blocks
        custom_blocks = self.block_manager.get_blocks_by_category('custom')
        for block in custom_blocks:
            block_id = block['id'].lower()
            sprite_path = self.block_manager.sprite_paths.get(block['id'], '')
            
            # Check if this sprite is from the bedrockandwater directory
            if 'bedrockandwater' in sprite_path.lower() or 'bedrock' in block_id:
                bedrock_block = block
                print(f"Using bedrock sprite: {block['id']} from {sprite_path}")
                break
        
        if not bedrock_block:
            print("Warning: No bedrock sprite found in bedrockandwater directory, using obsidian fallback")
            bedrock_block = self.block_manager.get_block_by_id('obsidian')
            if not bedrock_block:
                print("Error: No bedrock or obsidian block available")
                return
        
        # Create bedrock block data with proper bedrock pattern tiling
        block_data = {
            'id': bedrock_block['id'],
            'category': bedrock_block.get('category', 'custom'),
            'isBackground': False,
            'isBedrock': True,
            'tileSet': True,
            'tileMode': 'bedrock_pattern',
            'tileable': {'top': True, 'right': True, 'bottom': True, 'left': True}
        }
        
        # Place bedrock in bottom rows
        bedrock_rows = 6
        start_row = self.world_height - bedrock_rows
        
        for y in range(start_row, self.world_height):
            for x in range(self.world_width):
                self.layers[Layer.MIDGROUND][(x, y)] = block_data.copy()
        
        print(f"Placed {bedrock_block['id']} bedrock in bottom {bedrock_rows} rows")
        
        # Force chunk refresh in bedrock area
        if hasattr(self, 'chunk_manager') and self.chunk_manager is not None:
            for y in range(start_row, self.world_height, self.chunk_manager.chunk_size):
                for x in range(0, self.world_width, self.chunk_manager.chunk_size):
                    self.chunk_manager.invalidate_chunk(x, y)

    def save_state_for_undo(self, description: str):
        """Save current state for undo functionality"""
        if not self.batch_operation_active:
            self.undo_manager.save_state(self.layers, description)

    def start_batch_operation(self, description: str):
        """Start a batch operation (multiple changes treated as one undo step)"""
        self.batch_operation_active = True
        self.batch_operation_description = description

    def end_batch_operation(self):
        """End a batch operation and save state"""
        if self.batch_operation_active:
            self.undo_manager.save_state(self.layers, self.batch_operation_description)
            self.batch_operation_active = False
            self.batch_operation_description = ""
            
            # FIXED: Invalidate all chunks like clear_world does
            self.chunk_manager.invalidate_all_chunks()
            self.init_ui()

    def invalidate_brush_cache(self):
        """Invalidate brush spatial index when world changes significantly"""
        if hasattr(self, 'brush_manager'):
            self.brush_manager.invalidate_spatial_index()

    def debug_sprite_occupancy(self, block_id):
        """Debug method to check sprite occupancy calculation"""
        block = self.block_manager.get_block_by_id(block_id)
        if not block:
            print(f"Block '{block_id}' not found")
            return
            
        sprite = self.block_manager.get_sprite(block_id)
        if not sprite:
            print(f"Sprite for '{block_id}' not found")
            return
            
        tile_mode = block.get('tileMode', 'standard')
        bounds = self.tile_renderer.calculate_sprite_bounds(sprite, tile_mode)
        
        print(f"\n=== SPRITE OCCUPANCY DEBUG: {block_id} ===")
        print(f"Sprite size: {sprite.get_width()}x{sprite.get_height()} pixels")
        print(f"Tile mode: {tile_mode}")
        print(f"Occupied tiles (relative to origin): {bounds}")
        print(f"Total tiles occupied: {len(bounds)}")
        
        if len(bounds) > 1:
            print(f"Multi-tile sprite detected!")
        else:
            print(f"Single-tile sprite")
        print("=" * 50)

    def place_block(self, tile_x, tile_y, block_data):
        """Place a single block with collision detection and multi-tile occupancy tracking"""
        if not self.is_valid_position(tile_x, tile_y):
            return False
            
        if self.is_bedrock_position(tile_y):
            return False
        
        # Check for collisions with existing sprites on the same layer
        if self.tile_renderer.check_placement_collision(self, tile_x, tile_y, block_data, self.active_layer):
            return False
        
        # Place the block at origin position
        placed_block_data = block_data.copy()
        self.layers[self.active_layer][(tile_x, tile_y)] = placed_block_data
        
        # Clear selection after any block placement
        if self.selection:
            self.selection = None
            self.selection_start = None
            self.init_ui()
        
        # Get all tiles this sprite occupies and invalidate chunks
        sprite = self.block_manager.get_sprite(block_data.get('id', ''))
        occupied_tiles = self.tile_renderer.get_sprite_occupied_tiles(tile_x, tile_y, block_data, sprite)
        
        # FIXED: Force immediate chunk invalidation and reset cache state
        invalidated_chunks = set()
        for occupied_x, occupied_y in occupied_tiles:
            if self.is_valid_position(occupied_x, occupied_y):
                chunk_key = self.chunk_manager.get_chunk_key(occupied_x, occupied_y)
                if chunk_key not in invalidated_chunks:
                    chunk = self.chunk_manager.get_or_create_chunk(chunk_key[0], chunk_key[1])
                    chunk.dirty = True
                    chunk.blocks_hash = None  # Force hash recalculation
                    chunk.last_zoom = None   # Force zoom recalculation
                    chunk.surface = None     # Force surface recreation
                    invalidated_chunks.add(chunk_key)
        
        # Also invalidate neighboring chunks for seamless tiling
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                neighbor_x, neighbor_y = tile_x + dx, tile_y + dy
                if self.is_valid_position(neighbor_x, neighbor_y):
                    chunk_key = self.chunk_manager.get_chunk_key(neighbor_x, neighbor_y)
                    if chunk_key not in invalidated_chunks:
                        chunk = self.chunk_manager.get_or_create_chunk(chunk_key[0], chunk_key[1])
                        chunk.dirty = True
                        chunk.blocks_hash = None
                        invalidated_chunks.add(chunk_key)
        
        return True

    def erase_block_at_position(self, tile_x, tile_y):
        """Erase any sprite that occupies the given position"""
        if not self.is_valid_position(tile_x, tile_y):
            return False
        
        if self.is_bedrock_position(tile_y):
            return False
        
        # Find sprite that occupies this position
        origin_pos, block_data = self.tile_renderer.find_sprite_at_position(self, tile_x, tile_y, self.active_layer)
        
        if origin_pos is None:
            return False
        
        origin_x, origin_y = origin_pos
        
        # Get all tiles the sprite occupies before removing it
        sprite = self.block_manager.get_sprite(block_data.get('id', ''))
        occupied_tiles = self.tile_renderer.get_sprite_occupied_tiles(origin_x, origin_y, block_data, sprite)
        
        # Remove the sprite from the origin position
        if origin_pos in self.layers[self.active_layer]:
            del self.layers[self.active_layer][origin_pos]
        
        # FIXED: Force immediate chunk invalidation for all previously occupied tiles
        invalidated_chunks = set()
        for occupied_x, occupied_y in occupied_tiles:
            if self.is_valid_position(occupied_x, occupied_y):
                chunk_key = self.chunk_manager.get_chunk_key(occupied_x, occupied_y)
                if chunk_key not in invalidated_chunks:
                    chunk = self.chunk_manager.get_or_create_chunk(chunk_key[0], chunk_key[1])
                    chunk.dirty = True  # Force dirty flag
                    chunk.blocks_hash = None  # Reset hash to force re-computation
                    invalidated_chunks.add(chunk_key)
        
        return True

    def check_sprite_collision(self, tile_x, tile_y, block_data, layer):
        """Check if placing a sprite would collide with existing sprites"""
        return self.tile_renderer.check_placement_collision(self, tile_x, tile_y, block_data, layer)

    def init_ui(self):
        """Initialize the UI components with caching optimizations"""
        # Clear selection only if not using select or paste tool
        if self.active_tool not in [Tool.SELECT, Tool.PASTE]:
            if self.selection is not None or self.selection_start is not None:
                self.selection = None
                self.selection_start = None
        
        # Reset buttons
        self.buttons = {}
        self.toolbuttons = {}
    
        # Fixed buttons at the top of the toolbar
        button_y = 40
    
        # Tool buttons - first row
        tool_button_width = (self.toolbar_width - 20) // 4
        for i, tool in enumerate([Tool.PLACE, Tool.BRUSH, Tool.FILL, Tool.ERASE]):
            x = 10 + i * tool_button_width
            self.toolbuttons[tool] = {
                'rect': pygame.Rect(x, button_y, tool_button_width, 30),
                'text': tool.name.capitalize(),
                'active': tool == self.active_tool
            }
    
        button_y += 40
    
        # Tool buttons - second row (modified to include FLIP between SELECT and PASTE)
        tool_names = {
            Tool.SELECT: "Select",
            Tool.PASTE: "Paste", 
            Tool.EYEDROPPER: "Pick"
        }
    
        total_width = self.toolbar_width - 20
        button_gap = 5
        num_buttons = len(tool_names)
        button_width = (total_width - (button_gap * (num_buttons - 1))) // num_buttons
    
        for i, (tool, name) in enumerate(tool_names.items()):
            x = 10 + i * (button_width + button_gap)
            self.toolbuttons[tool] = {
                'rect': pygame.Rect(x, button_y, button_width, 30),
                'text': name,
                'active': tool == self.active_tool
            }
    
        button_y += 40
    
        # UNDO/REDO BUTTONS
        undo_redo_button_width = (self.toolbar_width - 30) // 2
        
        # Undo button
        undo_text = "Undo"
        if self.undo_manager.can_undo():
            undo_desc = self.undo_manager.get_undo_description()
            if undo_desc and len(undo_desc) < 15:
                undo_text = f"Undo: {undo_desc}"
        
        self.buttons['undo'] = {
            'rect': pygame.Rect(10, button_y, undo_redo_button_width, 30),
            'text': undo_text,
            'action': self.undo,
            'enabled': self.undo_manager.can_undo()
        }
    
        # Redo button
        redo_text = "Redo"
        if self.undo_manager.can_redo():
            redo_desc = self.undo_manager.get_redo_description()
            if redo_desc and len(redo_desc) < 15:
                redo_text = f"Redo: {redo_desc}"
        
        self.buttons['redo'] = {
            'rect': pygame.Rect(20 + undo_redo_button_width, button_y, undo_redo_button_width, 30),
            'text': redo_text,
            'action': self.redo,
            'enabled': self.undo_manager.can_redo()
        }
    
        button_y += 40
    
        # FLIP BUTTONS (only show when selection exists and tool is SELECT or PASTE)
        if self.selection and self.active_tool in [Tool.SELECT, Tool.PASTE]:
            flip_button_width = (self.toolbar_width - 30) // 2
            
            self.buttons['flip_x'] = {
                'rect': pygame.Rect(10, button_y, flip_button_width, 30),
                'text': 'Flip X',
                'action': self.flip_selection_horizontal
            }
    
            self.buttons['flip_y'] = {
                'rect': pygame.Rect(20 + flip_button_width, button_y, flip_button_width, 30),
                'text': 'Flip Y',
                'action': self.flip_selection_vertical
            }
    
            button_y += 40
    
        # Layer buttons
        layer_button_width = (self.toolbar_width - 30) // 2
        self.buttons['layer_bg'] = {
            'rect': pygame.Rect(10, button_y, layer_button_width, 30),
            'text': 'Background',
            'active': self.active_layer == Layer.BACKGROUND,
            'action': lambda: self.set_active_layer(Layer.BACKGROUND)
        }
    
        self.buttons['layer_mid'] = {
            'rect': pygame.Rect(20 + layer_button_width, button_y, layer_button_width, 30),
            'text': 'Foreground',
            'active': self.active_layer == Layer.MIDGROUND,
            'action': lambda: self.set_active_layer(Layer.MIDGROUND)
        }
    
        button_y += 40
    
        # WORLD BACKGROUND CONTROLS
        self.buttons['background_label'] = {
            'rect': pygame.Rect(10, button_y, self.toolbar_width - 20, 25),
            'text': f'World Background: {self.background_manager.get_current_background_name()}'
        }
        button_y += 35
    
        # Background selection buttons
        bg_button_width = (self.toolbar_width - 40) // 3
        
        self.buttons['bg_prev'] = {
            'rect': pygame.Rect(10, button_y, bg_button_width, 30),
            'text': '< Prev',
            'action': self.previous_background
        }
        
        self.buttons['bg_none'] = {
            'rect': pygame.Rect(15 + bg_button_width, button_y, bg_button_width, 30),
            'text': 'None',
            'action': lambda: self.set_background('none'),
            'active': self.background_manager.current_background == 'none'
        }
        
        self.buttons['bg_next'] = {
            'rect': pygame.Rect(20 + 2 * bg_button_width, button_y, bg_button_width, 30),
            'text': 'Next >',
            'action': self.next_background
        }
    
        button_y += 40
    
        # Add brush size buttons when brush tool is active - MODIFIED FOR CUSTOM INPUT
        if self.active_tool == Tool.BRUSH or self.active_tool == Tool.ERASE:
            self.buttons['brush_size_label'] = {
                'rect': pygame.Rect(10, button_y, self.toolbar_width - 20, 30),
                'text': f'Brush Size: {self.brush_size}'
            }
            button_y += 40
    
            size_button_width = (self.toolbar_width - 30) // 3
            
            # Buttons for size 1 and 3
            for i, size in enumerate([1, 3]):
                x = 10 + i * (size_button_width + 5)
                self.buttons[f'brush_size_{size}'] = {
                    'rect': pygame.Rect(x, button_y, size_button_width, 30),
                    'text': str(size),
                    'action': lambda s=size: self.set_brush_size(s),
                    'active': self.brush_size == size
                }
    
            # Custom input box instead of size 5 button
            x = 10 + 2 * (size_button_width + 5)
            display_text = f"Custom: {self.custom_brush_text}" if self.is_inputting_brush_size else f"Custom ({self.brush_size})" if self.brush_size not in [1, 3] else "Custom"
            self.buttons['brush_size_custom'] = {
                'rect': pygame.Rect(x, button_y, size_button_width, 30),
                'text': display_text,
                'action': self.activate_brush_size_input,
                'active': self.brush_size not in [1, 3],
                'is_custom_input': True
            }
    
            button_y += 40
    
            self.buttons['brush_square'] = {
                'rect': pygame.Rect(10, button_y, layer_button_width, 30),
                'text': 'Square',
                'action': lambda: self.set_brush_shape('square'),
                'active': self.brush_shape == 'square'
            }
    
            self.buttons['brush_circle'] = {
                'rect': pygame.Rect(20 + layer_button_width, button_y, layer_button_width, 30),
                'text': 'Circle',
                'action': lambda: self.set_brush_shape('circle'),
                'active': self.brush_shape == 'circle'
            }
    
            button_y += 40
    
        # Show/hide grid button
        self.buttons['toggle_grid'] = {
            'rect': pygame.Rect(10, button_y, layer_button_width, 30),
            'text': 'Toggle Grid',
            'action': self.toggle_grid
        }
    
        self.buttons['toggle_borders'] = {
            'rect': pygame.Rect(20 + layer_button_width, button_y, layer_button_width, 30),
            'text': 'Toggle Borders',
            'action': self.toggle_borders
        }
    
        button_y += 40
    
        # File operations
        self.buttons['save'] = {
            'rect': pygame.Rect(10, button_y, layer_button_width, 30),
            'text': 'Save World',
            'action': self.save_world
        }
    
        self.buttons['load'] = {
            'rect': pygame.Rect(20 + layer_button_width, button_y, layer_button_width, 30),
            'text': 'Load World',
            'action': self.load_world
        }
    
        button_y += 40
    
        self.buttons['export'] = {
            'rect': pygame.Rect(10, button_y, layer_button_width, 30),
            'text': 'Export Image',
            'action': self.export_image
        }
    
        self.buttons['clear'] = {
            'rect': pygame.Rect(20 + layer_button_width, button_y, layer_button_width, 30),
            'text': 'Clear World',
            'action': self.clear_world
        }
    
        button_y += 40
    
        # STATE CONTROLS
        if self.selected_block and 'tileMode' in self.selected_block:
            tile_mode = self.selected_block['tileMode']
            
            if tile_mode in ['2state', '4state'] and 'state' in self.selected_block and 'stateCount' in self.selected_block:
                state_text = self.get_state_display_text(self.selected_block)
                self.buttons['state_indicator'] = {
                    'rect': pygame.Rect(10, button_y, self.toolbar_width - 20, 30),
                    'text': state_text
                }
                button_y += 40
                
                self.buttons['prev_state'] = {
                    'rect': pygame.Rect(10, button_y, (self.toolbar_width - 30) // 2, 30),
                    'text': "< Prev",
                    'action': lambda: self.cycle_block_state(self.selected_block, -1)
                }
                
                self.buttons['next_state'] = {
                    'rect': pygame.Rect(20 + (self.toolbar_width - 30) // 2, button_y, (self.toolbar_width - 30) // 2, 30),
                    'text': "Next >",
                    'action': lambda: self.cycle_block_state(self.selected_block, 1)
                }
                button_y += 40
    
        self.buttons['upload_sprite'] = {
            'rect': pygame.Rect(10, button_y, self.toolbar_width - 20, 30),
            'text': 'Upload Sprites',
            'action': self.open_sprite_dialog
        }
    
        button_y += 40
        
        # Update notification
        if (hasattr(self, 'update_manager') and 
            self.update_manager is not None and 
            self.update_manager.update_available):
            self.buttons['update_available'] = {
                'rect': pygame.Rect(10, button_y, self.toolbar_width - 20, 30),
                'text': f'Update to version {self.update_manager.latest_version}',
                'action': self.install_update,
                'update_button': True
            }
            button_y += 40
    
        self.buttons['search_bar'] = {
            'rect': pygame.Rect(10, button_y, self.toolbar_width - 20, 30),
            'text': f'Search: {self.search_text}',
            'action': self.activate_search,
            'is_search': True
        }
    
        button_y += 40
    
        # Recent blocks section
        if self.recent_blocks:
            self.buttons['recent_blocks'] = {
                'rect': pygame.Rect(10, button_y, self.toolbar_width - 20, 30),
                'text': 'Recent Blocks'
            }
    
            button_y += 40
    
            block_size = 40
            padding = 5
            blocks_per_row = (self.toolbar_width - 20) // (block_size + padding)
    
            for j, block in enumerate(self.recent_blocks):
                row = j // blocks_per_row
                col = j % blocks_per_row
    
                x = 10 + col * (block_size + padding)
                y = button_y + row * (block_size + padding)
    
                self.buttons[f'recent_{j}'] = {
                    'rect': pygame.Rect(x, y, block_size, block_size),
                    'block': block,
                    'selected': block == self.selected_block,
                    'is_block': True
                }
    
            rows = (len(self.recent_blocks) + blocks_per_row - 1) // blocks_per_row
            button_y += rows * (block_size + padding) + 10
    
        # Add block categories
        button_y = self.add_block_categories(button_y)
    
        # Add auto-tiling information
        if self.selected_block and 'tileMode' in self.selected_block:
            tile_mode = self.selected_block['tileMode']
            mode_name = tile_mode.capitalize()
            
            self.buttons['tiling_info'] = {
                'rect': pygame.Rect(10, button_y, self.toolbar_width - 20, 30),
                'text': f"Tiling Mode: {mode_name}"
            }
            button_y += 40
    
        # Set the maximum scroll value
        self.toolbar_max_scroll = max(0, button_y - self.screen_height + 20)
        self.toolbar_scroll_y = min(self.toolbar_scroll_y, self.toolbar_max_scroll)
        
        # Mark UI cache as dirty after changes
        self.ui_cache_dirty = True

    def get_state_display_text(self, block):
        """Get display text for the current state of a multi-state block"""
        if 'state' in block and 'stateCount' in block:
            state = block.get('state', 0)
            state_count = block.get('stateCount', 2)
            return f"State: {state + 1}/{state_count}"
        return ""

    def add_block_categories(self, button_y):
        """Add block categories to the toolbar with optimizations"""
        category_order = ['custom']
        
        self.block_buttons = {}
        
        for category in category_order:
            if category not in self.block_manager.blocks:
                continue

            if category not in self.category_expanded:
                self.category_expanded[category] = True

            self.buttons[f'category_{category}'] = {
                'rect': pygame.Rect(10, button_y, self.toolbar_width - 20, 30),
                'text': category.capitalize() + ' Blocks',
                'action': lambda cat=category: self.toggle_category(cat),
                'category': category
            }

            button_y += 40

            if category not in self.block_buttons:
                self.block_buttons[category] = []
            else:
                self.block_buttons[category].clear()

            if self.category_expanded.get(category, True):
                blocks = self.block_manager.get_blocks_by_category(category)
                filtered_blocks = blocks
                
                if self.search_text:
                    search_lower = self.search_text.lower()
                    filtered_blocks = [b for b in blocks
                                     if search_lower in b['id'].lower()
                                     or search_lower in b['name'].lower()]

                block_size = 40
                padding = 5
                blocks_per_row = (self.toolbar_width - 20) // (block_size + padding)

                for j, block in enumerate(filtered_blocks):
                    row = j // blocks_per_row
                    col = j % blocks_per_row

                    x = 10 + col * (block_size + padding)
                    y = button_y + row * (block_size + padding)

                    self.block_buttons[category].append({
                        'rect': pygame.Rect(x, y, block_size, block_size),
                        'block': block,
                        'selected': block == self.selected_block
                    })

                rows = (len(filtered_blocks) + blocks_per_row - 1) // blocks_per_row if filtered_blocks else 0
                button_y += rows * (block_size + padding) + 10

        return button_y

    def toggle_category(self, category):
        """Toggle category expansion state"""
        self.category_expanded[category] = not self.category_expanded.get(category, True)
        self.init_ui()

    def toggle_grid(self):
        """Toggle grid visibility"""
        self.show_grid = not self.show_grid
        self.chunk_manager.invalidate_all_chunks()

    def toggle_borders(self):
        """Toggle block border visibility"""
        self.show_borders = not self.show_borders
        self.chunk_manager.invalidate_all_chunks()

    def set_brush_size(self, size):
        """Set the brush size"""
        self.brush_size = size
        self.init_ui()

    def set_brush_shape(self, shape):
        """Set the brush shape"""
        self.brush_shape = shape
        self.init_ui()

    def set_active_layer(self, layer):
        """Set the active layer and update UI"""
        self.active_layer = layer
        self.init_ui()

    def activate_search(self):
        """Activate the search bar for input"""
        self.is_searching = True
        self.search_cursor_pos = len(self.search_text)

    def activate_brush_size_input(self):
        """Activate the custom brush size input"""
        self.is_inputting_brush_size = True
        self.custom_brush_text = str(self.brush_size) if self.brush_size not in [1, 3] else ""
        self.custom_brush_cursor_pos = len(self.custom_brush_text)
        self.init_ui()

    def previous_background(self):
        """Switch to the previous background"""
        bg_list = self.background_manager.get_background_list()
        if len(bg_list) <= 1:
            return
        
        current_id = self.background_manager.current_background
        current_index = next((i for i, bg in enumerate(bg_list) if bg['id'] == current_id), 0)
        
        new_index = (current_index - 1) % len(bg_list)
        new_bg_id = bg_list[new_index]['id']
        
        self.background_manager.set_current_background(new_bg_id)
        self.init_ui()

    def next_background(self):
        """Switch to the next background"""
        bg_list = self.background_manager.get_background_list()
        if len(bg_list) <= 1:
            return
        
        current_id = self.background_manager.current_background
        current_index = next((i for i, bg in enumerate(bg_list) if bg['id'] == current_id), 0)
        
        new_index = (current_index + 1) % len(bg_list)
        new_bg_id = bg_list[new_index]['id']
        
        self.background_manager.set_current_background(new_bg_id)
        self.init_ui()

    def set_background(self, bg_id):
        """Set a specific background by ID"""
        self.background_manager.set_current_background(bg_id)
        self.init_ui()

    def save_world(self):
        """Save world data to a JSON file"""
        try:
            root = Tk()
            root.withdraw()
            
            file_path = filedialog.asksaveasfilename(
                title="Save World",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json")]
            )
            
            root.destroy()
            
            if file_path:
                save_data = {
                    'layers': {},
                    'world_width': self.world_width,
                    'world_height': self.world_height,
                    'bedrock_rows': self.bedrock_rows,
                    'background': self.background_manager.current_background
                }

                for layer_enum, layer_dict in self.layers.items():
                    layer_name = layer_enum.name
                    save_data['layers'][layer_name] = {}

                    for pos, block_data in layer_dict.items():
                        save_data['layers'][layer_name][f"{pos[0]},{pos[1]}"] = block_data

                with open(file_path, 'w') as f:
                    json.dump(save_data, f)
                print(f"World saved to {file_path}")
        except Exception as e:
            print(f"Error saving world: {e}")
            
    def perform_autosave(self):
        """Perform an autosave operation"""
        if not self.autosave_directory:
            return  # Autosave disabled
        
        try:
            # Create filename with timestamp
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"autosave_{timestamp}.json"
            filepath = os.path.join(self.autosave_directory, filename)
            
            # Use existing save logic
            save_data = {
                'layers': {},
                'world_width': self.world_width,
                'world_height': self.world_height,
                'bedrock_rows': self.bedrock_rows,
                'background': self.background_manager.current_background,
                'autosave': True,
                'timestamp': timestamp
            }
    
            for layer_enum, layer_dict in self.layers.items():
                layer_name = layer_enum.name
                save_data['layers'][layer_name] = {}
    
                for pos, block_data in layer_dict.items():
                    save_data['layers'][layer_name][f"{pos[0]},{pos[1]}"] = block_data
    
            with open(filepath, 'w') as f:
                json.dump(save_data, f)
            
            print(f"Autosaved to {filepath}")
            
            # Clean up old autosave files
            self.cleanup_old_autosaves()
            
        except Exception as e:
            print(f"Autosave failed: {e}")
    
    def cleanup_old_autosaves(self):
        """Remove old autosave files, keeping only the latest max_autosave_files"""
        if not self.autosave_directory or not os.path.exists(self.autosave_directory):
            return
        
        try:
            # Get all autosave files
            autosave_files = []
            for filename in os.listdir(self.autosave_directory):
                if filename.startswith("autosave_") and filename.endswith(".json"):
                    filepath = os.path.join(self.autosave_directory, filename)
                    if os.path.isfile(filepath):
                        # Get modification time
                        mtime = os.path.getmtime(filepath)
                        autosave_files.append((mtime, filepath))
            
            # Sort by modification time (newest first)
            autosave_files.sort(reverse=True)
            
            # Remove files beyond the limit
            files_to_remove = autosave_files[self.max_autosave_files:]
            for _, filepath in files_to_remove:
                try:
                    os.remove(filepath)
                    print(f"Removed old autosave: {os.path.basename(filepath)}")
                except Exception as e:
                    print(f"Could not remove old autosave {filepath}: {e}")
                    
        except Exception as e:
            print(f"Error during autosave cleanup: {e}")

    def create_block_data_from_selected(self):
        """Create block data from the currently selected block"""
        if not self.selected_block:
            return None
            
        block_data = {
            'id': self.selected_block['id'],
            'category': self.selected_block.get('category', 'custom'),
            'isBackground': self.selected_block.get('isBackground', False),
            'tileSet': self.selected_block.get('tileSet', False),
            'tileMode': self.selected_block.get('tileMode', 'standard'),
            'tileable': self.selected_block.get('tileable', {})
        }
        
        if 'state' in self.selected_block:
            block_data['state'] = self.selected_block['state']
            if 'stateCount' in self.selected_block:
                block_data['stateCount'] = self.selected_block['stateCount']
        
        return block_data

    def load_world(self):
        """Load world data from a JSON file"""
        try:
            root = Tk()
            root.withdraw()
            
            file_path = filedialog.askopenfilename(
                title="Load World",
                filetypes=[("JSON files", "*.json")]
            )
            
            root.destroy()
            
            if file_path:
                with open(file_path, 'r') as f:
                    save_data = json.load(f)

                self.layers = {
                    Layer.BACKGROUND: {},
                    Layer.MIDGROUND: {}
                }

                if 'layers' in save_data:
                    self.world_width = save_data.get('world_width', self.world_width)
                    self.world_height = save_data.get('world_height', self.world_height)
                    self.bedrock_rows = save_data.get('bedrock_rows', self.bedrock_rows)
                    
                    saved_background = save_data.get('background')
                    if saved_background:
                        self.background_manager.set_current_background(saved_background)

                    for layer_name, layer_dict in save_data['layers'].items():
                        if layer_name in ['BACKGROUND', 'MIDGROUND']:
                            layer_enum = Layer[layer_name]
                            for pos_str, block_data in layer_dict.items():
                                x, y = map(int, pos_str.split(','))
                                self.layers[layer_enum][(x, y)] = block_data

                print(f"World loaded from {file_path}")
                self.chunk_manager.invalidate_all_chunks()
                
                self.undo_manager.clear_history()
                self.undo_manager.save_state(self.layers, f"Loaded from {os.path.basename(file_path)}")
                self.init_ui()
                self.invalidate_brush_cache()
                
        except Exception as e:
            print(f"Error loading world: {e}")

    def export_image(self):
        """Export the world as a PNG image"""
        try:
            root = Tk()
            root.withdraw()
            
            file_path = filedialog.asksaveasfilename(
                title="Export Image",
                defaultextension=".png",
                filetypes=[("PNG files", "*.png")]
            )
            
            root.destroy()
            
            if file_path:
                width = self.world_width * self.tile_size
                height = self.world_height * self.tile_size
                
                export_surface = pygame.Surface((width, height))
                export_surface.fill((17, 17, 17))
                
                bg_surface = self.background_manager.get_current_background()
                if bg_surface:
                    scaled_bg = pygame.transform.scale(bg_surface, (width, height))
                    export_surface.blit(scaled_bg, (0, 0))
                
                # FIXED: Use proper render sorting like the chunk manager
                for layer_enum in [Layer.BACKGROUND, Layer.MIDGROUND]:
                    layer = self.layers[layer_enum]
                    
                    # Collect all blocks for this layer
                    layer_blocks = []
                    for (x, y), block_data in layer.items():
                        if 0 <= x < self.world_width and 0 <= y < self.world_height:
                            layer_blocks.append(((x, y), block_data))
                    
                    # Sort blocks for proper rendering order (same as chunk manager)
                    sorted_blocks = sorted(layer_blocks, key=lambda item: (
                        0 if item[1].get('isBackground', False) else 1,  # Background sprites first
                        0 if item[1].get('isBedrock', False) else 1,     # Bedrock sprites first
                        -item[0][1]  # Reverse Y for proper sprite layering (higher tiles on top)
                    ))
                    
                    # Render blocks in correct order
                    for (x, y), block_data in sorted_blocks:
                        screen_x = x * self.tile_size
                        screen_y = y * self.tile_size
                        
                        self.tile_renderer.draw_block_optimized(
                            export_surface, self, x, y, block_data,
                            screen_x, screen_y, self.tile_size, layer_enum
                        )
                
                pygame.image.save(export_surface, file_path)
                print(f"World exported to {file_path}")
        except Exception as e:
            print(f"Error exporting image: {e}")

    def clear_world(self):
        """Clear all blocks from the world"""
        self.save_state_for_undo("Clear world")
        
        self.layers = {
            Layer.BACKGROUND: {},
            Layer.MIDGROUND: {}
        }
        self.place_bedrock()
        self.chunk_manager.invalidate_all_chunks()
        self.init_ui()
        self.invalidate_brush_cache()

    def open_sprite_dialog(self):
        """Open a file dialog to upload sprites"""
        try:
            root = Tk()
            root.withdraw()
            
            file_paths = filedialog.askopenfilenames(
                title="Select Sprite Images",
                filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp")]
            )
            
            root.destroy()
            
            if file_paths:
                for file_path in file_paths:
                    self.block_manager.load_sprite_file(file_path)
                
                self.block_manager.update_custom_blocks()
                self.init_ui()
        except Exception as e:
            print(f"Error uploading sprites: {e}")

    def install_update(self):
        """Install available update"""
        if hasattr(self, 'update_manager') and self.update_manager.update_available:
            print(f"Installing update {self.update_manager.latest_version}...")
            if self.update_manager.download_and_install_update():
                print("Update installed, restarting...")
                self.running = False
    
    def get_current_version(self):
        """Get current application version"""
        return APP_VERSION

    def select_block(self, block):
        """Select a block for placement with optimizations"""
        self.selected_block = block
        
        # Auto-switch back from paste tool to previous tool when selecting new sprite
        if self.active_tool == Tool.PASTE:
            self.active_tool = self.previous_tool
            # Update tool button states
            for t, b in self.toolbuttons.items():
                b['active'] = (t == self.active_tool)
        
        # FIXED: Calculate and store sprite grid size for efficient flood fill
        if block:
            grid_width, grid_height = self.calculate_sprite_grid_size(block)
            self.selected_block['grid_width'] = grid_width
            self.selected_block['grid_height'] = grid_height
            print(f"Selected {block['id']}: grid size {grid_width}x{grid_height}")
        
        self.toolbar_scroll_y = 0
        
        for cat, btns in self.block_buttons.items():
            for btn in btns:
                btn['selected'] = (btn['block'] == block)
        
        if block not in self.recent_blocks:
            self.recent_blocks.insert(0, block)
            if len(self.recent_blocks) > 12:
                self.recent_blocks.pop()
        else:
            self.recent_blocks.remove(block)
            self.recent_blocks.insert(0, block)
        
        self.init_ui()

    def calculate_sprite_grid_size(self, block):
        """Calculate the grid size for placing sprites efficiently"""
        sprite = self.block_manager.get_sprite(block['id'])
        if not sprite:
            return (1, 1)  # Default to 1x1 grid
        
        tile_mode = block.get('tileMode', 'standard')
        bounds = self.tile_renderer.calculate_sprite_bounds(sprite, tile_mode)
        
        if not bounds:
            return (1, 1)
        
        # Calculate the maximum extents
        min_x = min(dx for dx, dy in bounds)
        max_x = max(dx for dx, dy in bounds)
        min_y = min(dy for dx, dy in bounds)
        max_y = max(dy for dx, dy in bounds)
        
        grid_width = max_x - min_x + 1
        grid_height = max_y - min_y + 1
        
        return (grid_width, grid_height)

    def get_scrollbar_rect(self):
        """Calculate scrollbar track rectangle"""
        if self.toolbar_max_scroll <= 0:
            return None
        
        scrollbar_x = self.toolbar_width - self.scrollbar_width - 2
        scrollbar_y = 40
        scrollbar_height = self.screen_height - 60
        
        return pygame.Rect(scrollbar_x, scrollbar_y, self.scrollbar_width, scrollbar_height)

    def get_scrollbar_thumb_rect(self):
        """Calculate scrollbar thumb rectangle"""
        track_rect = self.get_scrollbar_rect()
        if not track_rect or self.toolbar_max_scroll <= 0:
            return None
        
        visible_content_ratio = self.screen_height / (self.toolbar_max_scroll + self.screen_height)
        thumb_height = max(20, int(track_rect.height * visible_content_ratio))
        
        scroll_ratio = self.toolbar_scroll_y / self.toolbar_max_scroll
        thumb_y = track_rect.y + int((track_rect.height - thumb_height) * scroll_ratio)
        
        return pygame.Rect(track_rect.x, thumb_y, track_rect.width, thumb_height)

    def handle_scrollbar_click(self, pos):
        """Handle clicks on the scrollbar"""
        track_rect = self.get_scrollbar_rect()
        thumb_rect = self.get_scrollbar_thumb_rect()
        
        if not track_rect or not thumb_rect:
            return False
        
        if track_rect.collidepoint(pos):
            if thumb_rect.collidepoint(pos):
                self.is_dragging_scrollbar = True
                self.scrollbar_drag_offset = pos[1] - thumb_rect.y
                return True
            else:
                click_ratio = (pos[1] - track_rect.y) / track_rect.height
                self.toolbar_scroll_y = int(self.toolbar_max_scroll * click_ratio)
                self.toolbar_scroll_y = max(0, min(self.toolbar_max_scroll, self.toolbar_scroll_y))
                return True
        
        return False

    def handle_scrollbar_drag(self, pos):
        """Handle dragging the scrollbar thumb"""
        if not self.is_dragging_scrollbar:
            return
        
        track_rect = self.get_scrollbar_rect()
        thumb_rect = self.get_scrollbar_thumb_rect()
        
        if not track_rect or not thumb_rect:
            return
        
        new_thumb_y = pos[1] - self.scrollbar_drag_offset
        
        available_track = track_rect.height - thumb_rect.height
        if available_track > 0:
            thumb_ratio = (new_thumb_y - track_rect.y) / available_track
            self.toolbar_scroll_y = int(self.toolbar_max_scroll * thumb_ratio)
            self.toolbar_scroll_y = max(0, min(self.toolbar_max_scroll, self.toolbar_scroll_y))

    def handle_toolbar_click(self, pos, button):
        """Handle clicks on toolbar with optimizations"""
        if button == 4:  # Scroll up
            self.toolbar_scroll_y = max(0, self.toolbar_scroll_y - 20)
            return
        elif button == 5:  # Scroll down
            self.toolbar_scroll_y = min(self.toolbar_max_scroll, self.toolbar_scroll_y + 20)
            return
        
        if button == 1 and self.handle_scrollbar_click(pos):
            return

        adjusted_pos = (pos[0], pos[1] + self.toolbar_scroll_y)
        
        for name, button_data in self.buttons.items():
            if button_data['rect'].collidepoint(adjusted_pos):
                if 'is_search' in button_data and button_data.get('is_search', False):
                    self.activate_search()
                elif 'is_custom_input' in button_data and button_data.get('is_custom_input', False):
                    self.activate_brush_size_input()
                elif 'action' in button_data and button_data['action']:
                    if button_data.get('enabled', True):
                        button_data['action']()
                elif 'block' in button_data:
                    self.select_block(button_data['block'])
                return
        
        for tool, button_data in self.toolbuttons.items():
            if button_data['rect'].collidepoint(adjusted_pos):
                previous_tool = self.active_tool
                self.active_tool = tool
                
                if previous_tool != self.active_tool and self.active_tool != Tool.SELECT:
                    self.selection = None
                    self.selection_start = None
                
                for t, b in self.toolbuttons.items():
                    b['active'] = (t == tool)
                self.init_ui()
                return
        
        for category, blocks in self.block_buttons.items():
            if not self.category_expanded.get(category, True):
                continue
            
            for block_btn in blocks:
                if block_btn['rect'].collidepoint(adjusted_pos):
                    self.select_block(block_btn['block'])
                    return

    def handle_toolbar_hover(self, mouse_pos):
        """Handle hover events for tooltips with optimizations"""
        if mouse_pos[0] >= self.toolbar_width:
            self.tooltip_manager.clear_tooltip()
            return
            
        adjusted_pos = (mouse_pos[0], mouse_pos[1] + self.toolbar_scroll_y)
        tooltip_text = None
        
        # Check for block button hovers
        for category, blocks in self.block_buttons.items():
            if not self.category_expanded.get(category, True):
                continue
                
            for block_btn in blocks:
                if block_btn['rect'].collidepoint(adjusted_pos):
                    block = block_btn['block']
                    tooltip_text = block.get('name', block.get('id', 'Unknown'))
                    
                    tile_mode = block.get('tileMode', 'standard')
                    if tile_mode != 'standard':
                        tooltip_text += f" ({tile_mode})"
                    
                    if 'state' in block:
                        state = block.get('state', 0) + 1
                        state_count = block.get('stateCount', 2)
                        tooltip_text += f" [State {state}/{state_count}]"
                    
                    break
        
        if not tooltip_text:
            for name, button_data in self.buttons.items():
                if button_data['rect'].collidepoint(adjusted_pos):
                    tooltip_map = {
                        'toggle_grid': "Toggle grid display (G)",
                        'toggle_borders': "Toggle block borders",
                        'save': "Save world to file",
                        'load': "Load world from file",
                        'export': "Export world as image",
                        'clear': "Clear entire world",
                        'upload_sprite': "Upload custom sprite files",
                        'search_bar': "Search blocks (Ctrl+F)",
                        'undo': "Undo last action (Ctrl+Z)",
                        'redo': "Redo last undone action (Ctrl+Y)",
                        'bg_prev': "Previous background",
                        'bg_next': "Next background",
                        'bg_none': "No background",
                        'brush_size_custom': "Custom brush size (type size and press Enter)"
                    }
                    
                    if name in tooltip_map:
                        tooltip_text = tooltip_map[name]
                    elif name.startswith('brush_size_'):
                        tooltip_text = f"Set brush size to {button_data['text']}"
                    elif name in ['brush_square', 'brush_circle']:
                        tooltip_text = f"Set brush shape to {button_data['text'].lower()}"
                    break
        
        if not tooltip_text:
            for tool, button_data in self.toolbuttons.items():
                if button_data['rect'].collidepoint(adjusted_pos):
                    tool_name = tool.name.capitalize()
                    hotkey = self.get_tool_hotkey(tool)
                    tooltip_text = f"{tool_name} Tool"
                    if hotkey:
                        tooltip_text += f" ({hotkey})"
                    break
        
        if tooltip_text:
            self.tooltip_manager.set_tooltip(tooltip_text, mouse_pos)
        else:
            self.tooltip_manager.clear_tooltip()

    def get_tool_hotkey(self, tool):
        """Get hotkey for a tool"""
        hotkey_map = {
            Tool.PLACE: "P",
            Tool.BRUSH: "B", 
            Tool.FILL: "F",
            Tool.ERASE: "E",
            Tool.SELECT: "S",
            Tool.PASTE: "V",
            Tool.EYEDROPPER: "I"
        }
        return hotkey_map.get(tool, "")

    def render_world_optimized(self, surface):
        """Optimized world rendering with comprehensive performance monitoring"""
        render_start_time = pygame.time.get_ticks()
        
        # Clear canvas efficiently
        pygame.draw.rect(surface, (17, 17, 17), self.canvas_rect)
        
        # Draw world background first with advanced caching
        self.draw_world_background_optimized(surface)
        
        # Use consistent integer camera positions
        camera_x_int = int(round(self.camera_x))
        camera_y_int = int(round(self.camera_y))
        
        # Use optimized chunk manager to render the world
        self.chunk_manager.render_world_optimized(surface, camera_x_int, camera_y_int, self.zoom)
        
        # Draw world boundaries (optimized)
        effective_tile_size = int(self.tile_size * self.zoom)
        self.draw_world_boundaries_optimized(surface, camera_x_int, camera_y_int, effective_tile_size)
        
        # Draw UI overlays (only when needed)
        if self.selection or self.selection_start:
            self.draw_selection(surface)
            self.draw_selection_in_progress(surface)
        
        if self.active_tool in [Tool.BRUSH, Tool.ERASE]:
            self.draw_brush_preview(surface)
        
        self.draw_hover_indicator_optimized(surface, camera_x_int, camera_y_int, effective_tile_size)
        
        # Update performance stats
        self.performance_stats['render_time'] = pygame.time.get_ticks() - render_start_time

    def draw_world_background_optimized(self, surface):
        """Optimized world background drawing with advanced caching"""
        bg_surface = self.background_manager.get_current_background()
        if not bg_surface:
            return
        
        camera_x_int = int(round(self.camera_x))
        camera_y_int = int(round(self.camera_y))
        effective_tile_size = int(self.tile_size * self.zoom)
        
        # Calculate world dimensions
        world_width_px = self.world_width * effective_tile_size
        world_height_px = self.world_height * effective_tile_size
        
        # World position on screen
        world_screen_x = self.toolbar_width + self.resize_handle_width - camera_x_int
        world_screen_y = -camera_y_int
        
        # Advanced frustum culling - early exit if world is completely off-screen
        if (world_screen_x + world_width_px < self.toolbar_width + self.resize_handle_width or
            world_screen_x > self.screen_width or
            world_screen_y + world_height_px < 0 or
            world_screen_y > self.screen_height):
            return
        
        # Use advanced cached scaled background
        target_size = (world_width_px, world_height_px)
        scaled_bg = self.background_manager.get_current_background_cached(target_size)
        
        if scaled_bg:
            # Create optimized clipping area
            canvas_clip = pygame.Rect(
                self.toolbar_width + self.resize_handle_width, 0,
                self.screen_width - self.toolbar_width - self.resize_handle_width,
                self.screen_height
            )
            
            # Optimized clipping and drawing
            original_clip = surface.get_clip()
            surface.set_clip(canvas_clip)
            surface.blit(scaled_bg, (world_screen_x, world_screen_y))
            surface.set_clip(original_clip)

    def draw_world_boundaries_optimized(self, surface, camera_x_int, camera_y_int, effective_tile_size):
        """Optimized world boundary drawing with batch operations"""
        boundary_color = (255, 0, 0, 128)
        
        # Batch boundary calculations
        boundaries = []
        
        # Top boundary
        top_y = -camera_y_int
        if 0 <= top_y < self.screen_height:
            boundaries.append(('horizontal', top_y))
        
        # Bottom boundary
        bottom_y = self.world_height * effective_tile_size - camera_y_int
        if 0 <= bottom_y < self.screen_height:
            boundaries.append(('horizontal', bottom_y))
        
        # Left boundary
        left_x = self.toolbar_width + self.resize_handle_width - camera_x_int
        if self.toolbar_width + self.resize_handle_width <= left_x < self.screen_width:
            boundaries.append(('vertical', left_x))
        
        # Right boundary
        right_x = (self.world_width * effective_tile_size - camera_x_int + 
                  self.toolbar_width + self.resize_handle_width)
        if self.toolbar_width + self.resize_handle_width <= right_x < self.screen_width:
            boundaries.append(('vertical', right_x))
        
        # Batch draw all boundaries
        for boundary_type, pos in boundaries:
            if boundary_type == 'horizontal':
                pygame.draw.line(surface, boundary_color,
                               (self.toolbar_width + self.resize_handle_width, pos),
                               (self.screen_width, pos), 2)
            else:  # vertical
                pygame.draw.line(surface, boundary_color,
                               (pos, 0), (pos, self.screen_height), 2)

    def draw_hover_indicator_optimized(self, surface, camera_x_int, camera_y_int, effective_tile_size):
        """Optimized hover indicator drawing with smart collision detection"""
        mouse_x, mouse_y = pygame.mouse.get_pos()
        if not self.canvas_rect.collidepoint((mouse_x, mouse_y)):
            return
        
        if self.active_tool in [Tool.BRUSH, Tool.ERASE]:
            return  # Brush preview handles this
        
        canvas_x = mouse_x - self.toolbar_width - self.resize_handle_width
        
        tile_x = int((canvas_x + camera_x_int) / effective_tile_size)
        tile_y = int((mouse_y + camera_y_int) / effective_tile_size)
        
        if not self.is_valid_position(tile_x, tile_y):
            return
        
        hover_x = int(tile_x * effective_tile_size) - camera_x_int + self.toolbar_width + self.resize_handle_width
        hover_y = int(tile_y * effective_tile_size) - camera_y_int
        
        # Smart hover color determination
        if self.is_bedrock_position(tile_y):
            hover_color = (255, 0, 0)
            pygame.draw.rect(surface, hover_color, (hover_x, hover_y, effective_tile_size, effective_tile_size), 2)
        elif self.active_tool == Tool.PLACE and self.selected_block:
            block_data = self.create_block_data_from_selected()
            if block_data:
                sprite = self.block_manager.get_sprite(block_data.get('id', ''))
                occupied_tiles = self.tile_renderer.get_sprite_occupied_tiles(tile_x, tile_y, block_data, sprite)
                
                has_collision = self.check_sprite_collision(tile_x, tile_y, block_data, self.active_layer)
                hover_color = (255, 100, 0) if has_collision else (0, 255, 0)
                
                # Optimized multi-tile preview drawing
                for occupied_x, occupied_y in occupied_tiles:
                    if self.is_valid_position(occupied_x, occupied_y):
                        preview_x = int(occupied_x * effective_tile_size) - camera_x_int + self.toolbar_width + self.resize_handle_width
                        preview_y = int(occupied_y * effective_tile_size) - camera_y_int
                        
                        line_width = 3 if (occupied_x, occupied_y) == (tile_x, tile_y) else 2
                        pygame.draw.rect(surface, hover_color, (preview_x, preview_y, effective_tile_size, effective_tile_size), line_width)
        else:
            hover_color = (255, 204, 0)
            pygame.draw.rect(surface, hover_color, (hover_x, hover_y, effective_tile_size, effective_tile_size), 2)

    def draw_selection(self, surface):
        """Draw selection rectangle with optimizations"""
        if not self.selection:
            return

        x, y, width, height = self.selection
        effective_tile_size = self.tile_size * self.zoom

        screen_x = x * effective_tile_size - self.camera_x + self.toolbar_width + self.resize_handle_width
        screen_y = y * effective_tile_size - self.camera_y
        screen_width = width * effective_tile_size
        screen_height = height * effective_tile_size

        selection_rect = pygame.Rect(screen_x, screen_y, screen_width, screen_height)

        # Frustum culling check
        if (screen_x + screen_width < self.toolbar_width + self.resize_handle_width or
                screen_x > self.screen_width or
                screen_y + screen_height < 0 or
                screen_y > self.screen_height):
            return

        # Draw selection rectangle
        pygame.draw.rect(surface, (255, 255, 0), selection_rect, 2)

        # Draw resize handles
        handle_size = 6
        handle_color = (255, 255, 0)
        handle_positions = [
            (screen_x - handle_size // 2, screen_y - handle_size // 2),
            (screen_x + screen_width - handle_size // 2, screen_y - handle_size // 2),
            (screen_x - handle_size // 2, screen_y + screen_height - handle_size // 2),
            (screen_x + screen_width - handle_size // 2, screen_y + screen_height - handle_size // 2)
        ]
        
        for pos in handle_positions:
            pygame.draw.rect(surface, handle_color, (*pos, handle_size, handle_size))

    def draw_selection_in_progress(self, surface):
        """Draw selection in progress with optimizations"""
        if not self.selection_start:
            return

        mouse_pos = pygame.mouse.get_pos()
        effective_tile_size = self.tile_size * self.zoom

        start_x = int((self.selection_start[0] - self.toolbar_width - self.resize_handle_width + self.camera_x) / effective_tile_size)
        start_y = int((self.selection_start[1] + self.camera_y) / effective_tile_size)

        end_x = int((mouse_pos[0] - self.toolbar_width - self.resize_handle_width + self.camera_x) / effective_tile_size)
        end_y = int((mouse_pos[1] + self.camera_y) / effective_tile_size)

        if start_x > end_x:
            start_x, end_x = end_x, start_x
        if start_y > end_y:
            start_y, end_y = end_y, start_y

        screen_start_x = start_x * effective_tile_size - self.camera_x + self.toolbar_width + self.resize_handle_width
        screen_start_y = start_y * effective_tile_size - self.camera_y
        screen_width = (end_x - start_x + 1) * effective_tile_size
        screen_height = (end_y - start_y + 1) * effective_tile_size

        selection_rect = pygame.Rect(screen_start_x, screen_start_y, screen_width, screen_height)
        pygame.draw.rect(surface, (255, 255, 0), selection_rect, 2)

    def draw_brush_preview(self, surface):
        """Draw brush preview with optimized collision checking"""
        if self.active_tool not in [Tool.BRUSH, Tool.ERASE]:
            return
        
        mouse_pos = pygame.mouse.get_pos()
        if not self.canvas_rect.collidepoint(mouse_pos):
            return
        
        effective_tile_size = self.tile_size * self.zoom
        
        # FIXED: Use exact same coordinate calculation as actual placement
        canvas_x = mouse_pos[0] - self.toolbar_width - self.resize_handle_width
        
        # Convert to integers first like in handle_mouse_click
        camera_x_int = int(round(self.camera_x))
        camera_y_int = int(round(self.camera_y))
        
        tile_x = int((canvas_x + self.camera_x) / effective_tile_size)
        tile_y = int((mouse_pos[1] + self.camera_y) / effective_tile_size)
        
        if self.active_tool == Tool.BRUSH and self.selected_block:
            # Use optimized collision preview
            collision_info = self.brush_manager.get_brush_collision_preview(tile_x, tile_y)
            
            for (brush_x, brush_y), info in collision_info.items():
                has_collision = info['has_collision']
                aligned_x, aligned_y = info['aligned_pos']
                sprite_bounds = info['sprite_bounds']
                
                # Color based on collision
                outline_color = (255, 100, 0) if has_collision else (0, 255, 0)
                
                # Draw sprite bounds
                for bound_dx, bound_dy in sprite_bounds:
                    occupied_x = aligned_x + bound_dx
                    occupied_y = aligned_y + bound_dy
                    
                    if self.is_valid_position(occupied_x, occupied_y):
                        occupied_screen_x = int(occupied_x * effective_tile_size) - int(self.camera_x) + self.toolbar_width + self.resize_handle_width
                        occupied_screen_y = int(occupied_y * effective_tile_size) - int(self.camera_y)
                        
                        # Outline thickness (origin gets thicker outline)
                        outline_width = 3 if (bound_dx, bound_dy) == (0, 0) else 2
                        preview_rect = pygame.Rect(occupied_screen_x, occupied_screen_y, effective_tile_size, effective_tile_size)
                        pygame.draw.rect(surface, outline_color, preview_rect, outline_width)
        else:
            # Erase mode - simple pattern
            pattern = self.brush_manager.get_brush_pattern(self.brush_size, self.brush_shape)
            
            for dx, dy in pattern:
                brush_tile_x, brush_tile_y = tile_x + dx, tile_y + dy
                
                if not self.is_valid_position(brush_tile_x, brush_tile_y):
                    continue
                if self.is_bedrock_position(brush_tile_y):
                    continue
                
                screen_x = int(brush_tile_x * effective_tile_size) - camera_x_int + self.toolbar_width + self.resize_handle_width
                screen_y = int(brush_tile_y * effective_tile_size) - camera_y_int
                
                preview_rect = pygame.Rect(screen_x, screen_y, effective_tile_size, effective_tile_size)
                pygame.draw.rect(surface, (255, 0, 0), preview_rect, 2)

    def draw_toolbar(self, surface):
        """Draw the toolbar with advanced caching and optimizations"""
        # Draw toolbar background
        pygame.draw.rect(surface, (51, 51, 51), (0, 0, self.toolbar_width, self.screen_height))
    
        # Draw title
        title_surface, title_rect = self.font.render("Crystal Realms World Planner", (255, 255, 255))
        surface.blit(title_surface, (self.toolbar_width // 2 - title_rect.width // 2, 10))
    
        # Create clipping rect for toolbar content
        content_width = self.toolbar_width - self.scrollbar_width - 4
        toolbar_clip = pygame.Rect(0, 0, content_width, self.screen_height)
        previous_clip = surface.get_clip()
        surface.set_clip(toolbar_clip)
    
        scroll_offset = -self.toolbar_scroll_y
    
        # Optimized button drawing with culling
        self.draw_buttons_optimized(surface, scroll_offset)
        self.draw_tool_buttons_optimized(surface, scroll_offset)
        self.draw_block_buttons_optimized(surface, scroll_offset)
    
        # Reset clip
        surface.set_clip(previous_clip)
    
        # Draw scrollbar
        self.draw_scrollbar(surface)
    
        # Draw coordinate display
        if self.show_coordinates:
            coord_text = f"X: {self.mouse_grid_x}  Y: {self.mouse_grid_y}"
            coord_surface, coord_rect = self.font_small.render(coord_text, (255, 255, 255))
            surface.blit(coord_surface, (self.toolbar_width // 2.35 - title_rect.width // 2, 27.5))
    
        # Draw version display
        version_text = f"v{APP_VERSION}"
        version_surface, version_rect = self.font_small.render(version_text, (180, 180, 180))
        surface.blit(version_surface, (self.toolbar_width // 0.79 - title_rect.width // 2, 10))
    
        # Draw resize handle
        self.draw_resize_handle(surface)

    def draw_buttons_optimized(self, surface, scroll_offset):
        """Optimized button drawing with frustum culling"""
        for name, button_data in self.buttons.items():
            # Frustum culling - skip if completely out of view
            if button_data['rect'].bottom + scroll_offset < 0 or button_data['rect'].top + scroll_offset > self.screen_height:
                continue

            adjusted_rect = button_data['rect'].copy()
            adjusted_rect.y += scroll_offset

            # Determine colors efficiently
            is_disabled = not button_data.get('enabled', True)
            if is_disabled:
                button_color, text_color = (40, 40, 40), (128, 128, 128)
            elif button_data.get('update_button', False):
                button_color, text_color = (34, 139, 34), (255, 255, 255)  # Green for updates
            elif name.startswith('category_'):
                button_color, text_color = (85, 85, 85), (255, 255, 255)
            elif button_data.get('active', False):
                button_color, text_color = (0, 102, 204), (255, 255, 255)
            elif (self.is_searching and name == 'search_bar') or (self.is_inputting_brush_size and name == 'brush_size_custom'):
                button_color, text_color = (0, 120, 215), (255, 255, 255)
            else:
                button_color, text_color = (68, 68, 68), (255, 255, 255)

            # Draw button
            pygame.draw.rect(surface, button_color, adjusted_rect)

            # Handle different button types
            if 'is_block' in button_data and button_data['is_block']:
                self.draw_block_button_content(surface, button_data, adjusted_rect)
            elif 'text' in button_data:
                self.draw_text_button_content(surface, button_data, adjusted_rect, text_color, name)

    def draw_block_button_content(self, surface, button_data, rect):
        """Draw block button content with sprite caching"""
        block = button_data['block']
        
        # Draw border
        border_color = (255, 204, 0) if button_data.get('selected', False) else (102, 102, 102)
        pygame.draw.rect(surface, border_color, rect, 2)

        # Draw block content
        inner_rect = pygame.Rect(rect.x + 4, rect.y + 4, rect.width - 8, rect.height - 8)

        sprite = self.block_manager.get_sprite(block['id'])
        if sprite:
            # Use sprite cache for scaled sprites
            cache_key = (block['id'], inner_rect.width, inner_rect.height)
            
            if cache_key in self.ui_surface_cache:
                scaled_sprite = self.ui_surface_cache[cache_key]
            else:
                scaled_sprite = pygame.transform.scale(sprite, (inner_rect.width, inner_rect.height))
                scaled_sprite = scaled_sprite.convert_alpha()
                
                # Limit cache size
                if len(self.ui_surface_cache) > 200:
                    oldest_key = next(iter(self.ui_surface_cache))
                    del self.ui_surface_cache[oldest_key]
                
                self.ui_surface_cache[cache_key] = scaled_sprite
            
            surface.blit(scaled_sprite, inner_rect)
        else:
            pygame.draw.rect(surface, block['color'], inner_rect)

    def draw_text_button_content(self, surface, button_data, adjusted_rect, text_color, name):
        """Draw text button content with search cursor and custom brush input cursor"""
        text_surface, text_rect = self.font.render(button_data['text'], text_color)
        text_x = adjusted_rect.x + (adjusted_rect.width // 2) - (text_rect.width // 2)
        text_y = adjusted_rect.y + (adjusted_rect.height // 2) - (text_rect.height // 2)

        surface.blit(text_surface, (text_x, text_y))

        # Draw search cursor if active
        if name == 'search_bar' and self.is_searching:
            self.draw_search_cursor(surface, text_x, text_y, text_rect, text_color)
        
        # Draw custom brush size cursor if active
        elif name == 'brush_size_custom' and self.is_inputting_brush_size:
            self.draw_brush_size_cursor(surface, text_x, text_y, text_rect, text_color)

    def draw_search_cursor(self, surface, text_x, text_y, text_rect, text_color):
        """Draw search cursor with optimized positioning"""
        prefix_text = "Search: "
        prefix_surface, prefix_rect = self.font.render(prefix_text, text_color)
        prefix_width = prefix_rect.width
        
        search_text_surface, search_rect = self.font.render(self.search_text[:self.search_cursor_pos], text_color)
        search_text_width = search_rect.width

        cursor_x = text_x + prefix_width + search_text_width
        cursor_y = text_y
        cursor_height = text_rect.height

        if pygame.time.get_ticks() % 1000 < 500:  # Blink cursor
            pygame.draw.line(surface, (255, 255, 255),
                            (cursor_x, cursor_y),
                            (cursor_x, cursor_y + cursor_height), 2)

    def draw_brush_size_cursor(self, surface, text_x, text_y, text_rect, text_color):
        """Draw custom brush size input cursor"""
        prefix_text = "Custom: "
        prefix_surface, prefix_rect = self.font.render(prefix_text, text_color)
        prefix_width = prefix_rect.width
        
        brush_text_surface, brush_rect = self.font.render(self.custom_brush_text[:self.custom_brush_cursor_pos], text_color)
        brush_text_width = brush_rect.width

        cursor_x = text_x + prefix_width + brush_text_width
        cursor_y = text_y
        cursor_height = text_rect.height

        if pygame.time.get_ticks() % 1000 < 500:  # Blink cursor
            pygame.draw.line(surface, (255, 255, 255),
                            (cursor_x, cursor_y),
                            (cursor_x, cursor_y + cursor_height), 2)

    def draw_tool_buttons_optimized(self, surface, scroll_offset):
        """Optimized tool button drawing"""
        for tool, button_data in self.toolbuttons.items():
            if button_data['rect'].bottom + scroll_offset < 0 or button_data['rect'].top + scroll_offset > self.screen_height:
                continue

            adjusted_rect = button_data['rect'].copy()
            adjusted_rect.y += scroll_offset

            button_color = (0, 102, 204) if button_data['active'] else (68, 68, 68)
            pygame.draw.rect(surface, button_color, adjusted_rect)

            text_surface, text_rect = self.font.render(button_data['text'], (255, 255, 255))
            text_x = adjusted_rect.x + (adjusted_rect.width // 2) - (text_rect.width // 2)
            text_y = adjusted_rect.y + (adjusted_rect.height // 2) - (text_rect.height // 2)

            surface.blit(text_surface, (text_x, text_y))

    def draw_block_buttons_optimized(self, surface, scroll_offset):
        """Optimized block button drawing with batch operations"""
        for category, blocks in self.block_buttons.items():
            if not self.category_expanded.get(category, True):
                continue

            for block_btn in blocks:
                if block_btn['rect'].bottom + scroll_offset < 0 or block_btn['rect'].top + scroll_offset > self.screen_height:
                    continue

                block = block_btn['block']
                adjusted_rect = block_btn['rect'].copy()
                adjusted_rect.y += scroll_offset

                # Draw background and border
                border_color = (255, 204, 0) if block_btn['selected'] else (102, 102, 102)
                pygame.draw.rect(surface, (51, 51, 51), adjusted_rect)
                pygame.draw.rect(surface, border_color, adjusted_rect, 2)

                # Draw block content with caching
                inner_rect = pygame.Rect(adjusted_rect.x + 4, adjusted_rect.y + 4, 
                                       adjusted_rect.width - 8, adjusted_rect.height - 8)

                sprite = self.block_manager.get_sprite(block['id'])
                if sprite:
                    cache_key = (block['id'], inner_rect.width, inner_rect.height)
                    
                    if cache_key in self.ui_surface_cache:
                        scaled_sprite = self.ui_surface_cache[cache_key]
                    else:
                        scaled_sprite = pygame.transform.scale(sprite, (inner_rect.width, inner_rect.height))
                        scaled_sprite = scaled_sprite.convert_alpha()
                        
                        if len(self.ui_surface_cache) > 200:
                            oldest_key = next(iter(self.ui_surface_cache))
                            del self.ui_surface_cache[oldest_key]
                        
                        self.ui_surface_cache[cache_key] = scaled_sprite
                    
                    surface.blit(scaled_sprite, inner_rect)
                else:
                    pygame.draw.rect(surface, block['color'], inner_rect)

    def draw_scrollbar(self, surface):
        """Draw the scrollbar track and thumb with optimizations"""
        if self.toolbar_max_scroll <= 0:
            return

        track_rect = self.get_scrollbar_rect()
        thumb_rect = self.get_scrollbar_thumb_rect()
        
        if not track_rect or not thumb_rect:
            return

        # Draw track
        pygame.draw.rect(surface, self.scrollbar_track_color, track_rect)
        pygame.draw.rect(surface, (100, 100, 100), track_rect, 1)

        # Draw thumb with hover effect
        mouse_pos = pygame.mouse.get_pos()
        thumb_color = self.scrollbar_thumb_hover_color if thumb_rect.collidepoint(mouse_pos) else self.scrollbar_thumb_color
        
        pygame.draw.rect(surface, thumb_color, thumb_rect)
        pygame.draw.rect(surface, (180, 180, 180), thumb_rect, 1)

    def draw_resize_handle(self, surface):
        """Draw a resize handle for the toolbar"""
        handle_rect = pygame.Rect(
            self.toolbar_width, 0,
            self.resize_handle_width, self.screen_height
        )

        # Draw handle background
        pygame.draw.rect(surface, (80, 80, 80), handle_rect)

        # Draw grip lines
        line_color = (120, 120, 120)
        for y in range(20, self.screen_height - 20, 20):
            pygame.draw.line(surface, line_color,
                             (self.toolbar_width + 2, y),
                             (self.toolbar_width + self.resize_handle_width - 2, y), 1)

    def is_valid_position(self, x, y):
        """Check if position is within world boundaries"""
        return 0 <= x < self.world_width and 0 <= y < self.world_height

    def is_bedrock_position(self, y):
        """Check if position is in bedrock area"""
        return y >= self.world_height - self.bedrock_rows

    def handle_mouse_click(self, pos, button):
        """Handle mouse click events with optimizations"""
        # Check if click is on resize handle
        if button == 1 and self.is_point_on_resize_handle(pos):
            self.is_resizing_toolbar = True
            return
    
        # Handle toolbar interactions
        if pos[0] < self.toolbar_width:
            self.handle_toolbar_click(pos, button)
            return
    
        # If we're in search mode or brush input mode and click outside, deactivate it
        if (self.is_searching or self.is_inputting_brush_size) and pos[0] >= self.toolbar_width:
            self.is_searching = False
            self.is_inputting_brush_size = False
            return
    
        # Handle canvas clicks
        if self.canvas_rect.collidepoint(pos):
            if self.is_searching or self.is_inputting_brush_size:
                self.is_searching = False
                self.is_inputting_brush_size = False
    
            # Convert to tile coordinates
            effective_tile_size = self.tile_size * self.zoom
            canvas_x = pos[0] - self.toolbar_width - self.resize_handle_width
            
            tile_x = int((canvas_x + self.camera_x) / effective_tile_size)
            tile_y = int((pos[1] + self.camera_y) / effective_tile_size)
            
            # Handle right clicks - always enables panning
            if button == 3:
                if self.active_tool == Tool.SELECT:
                    if self.selection_start:
                        self.handle_selection(self.selection_start, pos)
                        self.selection_start = None
                        self.copy_selection()
                        return
                self.is_dragging = True
                self.last_mouse_pos = pos
                # Capture mouse during panning
                pygame.event.set_grab(True)
                return
    
            # Handle left clicks for various tools
            if button == 1:
                if self.active_tool == Tool.SELECT:
                    if not self.is_valid_position(tile_x, tile_y):
                        return
                    self.selection_start = pos
    
                elif self.active_tool == Tool.PLACE and self.selected_block:
                    if not self.is_valid_position(tile_x, tile_y):
                        return
                    if self.is_bedrock_position(tile_y):
                        return
    
                    block_data = self.create_block_data_from_selected()
                    if block_data:
                        self.start_batch_operation(f"Place {block_data['id']}")
                        if self.place_block(tile_x, tile_y, block_data):
                            self.end_batch_operation()
    
                elif self.active_tool == Tool.BRUSH and self.selected_block:
                    if not self.is_valid_position(tile_x, tile_y):
                        return
    
                    block_data = self.create_block_data_from_selected()
                    if block_data:
                        self.start_batch_operation(f"Brush {block_data['id']}")
                        self.place_blocks_with_brush(tile_x, tile_y, block_data)
    
                elif self.active_tool == Tool.ERASE:
                    if not self.is_valid_position(tile_x, tile_y):
                        return
                    if self.is_bedrock_position(tile_y):
                        return
    
                    if self.brush_size > 1:
                        self.start_batch_operation("Erase with brush")
                        self.erase_blocks_with_brush(tile_x, tile_y)
                    else:
                        if self.erase_block_at_position(tile_x, tile_y):
                            self.save_state_for_undo("Erase block")
                            # FIXED: Add immediate visual updates for single erase
                            self.chunk_manager.force_update_affected_chunks([(tile_x, tile_y)])
                            self.force_immediate_chunk_update()
    
                elif self.active_tool == Tool.FILL and self.selected_block:
                    if not self.is_valid_position(tile_x, tile_y):
                        return
    
                    target_block = self.layers[self.active_layer].get((tile_x, tile_y), None)
                    block_data = self.create_block_data_from_selected()
                    if block_data:
                        self.start_batch_operation(f"Fill with {block_data['id']}")
                        self.flood_fill(tile_x, tile_y, target_block, block_data)
                        self.end_batch_operation()
    
                elif self.active_tool == Tool.PASTE:
                    if not self.clipboard:
                        print("Nothing to paste")
                        return
                    self.save_state_for_undo("Paste selection")
                    self.paste_selection(tile_x, tile_y)
    
                elif self.active_tool == Tool.EYEDROPPER:
                    if not self.is_valid_position(tile_x, tile_y):
                        return
                
                    # Check active layer first, then other layer
                    layers_to_check = [self.active_layer]
                    other_layer = Layer.BACKGROUND if self.active_layer == Layer.MIDGROUND else Layer.MIDGROUND
                    layers_to_check.append(other_layer)
                    
                    for layer_enum in layers_to_check:
                        origin_pos, block_data = self.tile_renderer.find_sprite_at_position(self, tile_x, tile_y, layer_enum)
                        if origin_pos is not None:
                            block_id = block_data.get('id', '')
                            block_def = self.block_manager.get_block_by_id(block_id)
                            if block_def:
                                self.select_block(block_def)
                                self.active_layer = layer_enum
                                self.init_ui()
                                return

    def handle_selection(self, start_pos, end_pos):
        """Create a selection box from start to end position"""
        if not start_pos or not end_pos:
            return

        effective_tile_size = self.tile_size * self.zoom

        start_x = int((start_pos[0] - self.toolbar_width - self.resize_handle_width + self.camera_x) / effective_tile_size)
        start_y = int((start_pos[1] + self.camera_y) / effective_tile_size)

        end_x = int((end_pos[0] - self.toolbar_width - self.resize_handle_width + self.camera_x) / effective_tile_size)
        end_y = int((end_pos[1] + self.camera_y) / effective_tile_size)

        if start_x > end_x:
            start_x, end_x = end_x, start_x
        if start_y > end_y:
            start_y, end_y = end_y, start_y

        start_x = max(0, start_x)
        start_y = max(0, start_y)
        end_x = min(self.world_width - 1, end_x)
        end_y = min(self.world_height - 1, end_y)

        width = end_x - start_x + 1
        height = end_y - start_y + 1

        self.selection = (start_x, start_y, width, height)

    def copy_selection(self):
        """Copy selected blocks to clipboard"""
        if not self.selection:
            return
    
        x, y, width, height = self.selection
    
        self.clipboard = {
            Layer.BACKGROUND: {},
            Layer.MIDGROUND: {},
        }
    
        total_copied = 0
    
        for layer_enum, layer_dict in self.layers.items():
            for pos, block_data in layer_dict.items():
                px, py = pos
                if x <= px < x + width and y <= py < y + height:
                    rel_x = px - x
                    rel_y = py - y
                    self.clipboard[layer_enum][(rel_x, rel_y)] = block_data.copy()
                    total_copied += 1
    
        if total_copied > 0:
            # Store the current tool before switching to paste
            if self.active_tool in [Tool.PLACE, Tool.BRUSH]:
                self.previous_tool = self.active_tool
            self.active_tool = Tool.PASTE
            self.init_ui()

    def flip_selection_horizontal(self):
        """Flip selection horizontally (mirror left-right) - accounts for multi-tile sprites"""
        if not self.selection:
            return
            
        self.save_state_for_undo("Flip selection horizontally")
        
        x, y, width, height = self.selection
        
        # Step 1: Collect all sprites and calculate their bounds within the selection
        sprites_to_move = []
        positions_to_clear = []
        
        for layer_enum in [Layer.BACKGROUND, Layer.MIDGROUND]:
            layer = self.layers[layer_enum]
            for pos, block_data in list(layer.items()):
                px, py = pos
                if x <= px < x + width and y <= py < y + height:
                    # Get sprite bounds to understand its footprint
                    sprite = self.block_manager.get_sprite(block_data.get('id', ''))
                    if sprite:
                        tile_mode = block_data.get('tileMode', 'standard')
                        sprite_bounds = self.tile_renderer.calculate_sprite_bounds(sprite, tile_mode)
                        
                        # Find the rightmost tile this sprite occupies
                        max_dx = max(dx for dx, dy in sprite_bounds) if sprite_bounds else 0
                        sprite_width = max_dx + 1
                        
                        # Calculate relative position within selection
                        rel_x = px - x
                        rel_y = py - y
                        
                        # Flip horizontally: place the sprite so its RIGHT edge is where the LEFT edge was
                        flipped_rel_x = (width - 1) - (rel_x + sprite_width - 1)
                        new_pos = (x + flipped_rel_x, y + rel_y)
                    else:
                        # Single tile sprite fallback
                        rel_x = px - x
                        rel_y = py - y
                        flipped_rel_x = width - 1 - rel_x
                        new_pos = (x + flipped_rel_x, y + rel_y)
                    
                    if self.is_valid_position(new_pos[0], new_pos[1]) and not self.is_bedrock_position(new_pos[1]):
                        sprites_to_move.append((layer_enum, new_pos, block_data.copy()))
                    
                    positions_to_clear.append((layer_enum, pos))
        
        # Step 2: Clear all original positions
        for layer_enum, pos in positions_to_clear:
            if pos in self.layers[layer_enum]:
                del self.layers[layer_enum][pos]
        
        # Step 3: Place all sprites in their new positions
        affected_positions = []
        for layer_enum, new_pos, block_data in sprites_to_move:
            self.layers[layer_enum][new_pos] = block_data
            affected_positions.append(new_pos)
        
        # Step 4: Update chunks
        if affected_positions:
            self.chunk_manager.force_update_affected_chunks(affected_positions)
            self.force_immediate_chunk_update()
    
    def flip_selection_vertical(self):
        """Flip selection vertically (mirror top-bottom) - accounts for multi-tile sprites"""
        if not self.selection:
            return
            
        self.save_state_for_undo("Flip selection vertically")
        
        x, y, width, height = self.selection
        
        # Step 1: Collect all sprites and find the range of Y positions
        sprites_to_move = []
        positions_to_clear = []
        y_positions = []
        
        for layer_enum in [Layer.BACKGROUND, Layer.MIDGROUND]:
            layer = self.layers[layer_enum]
            for pos, block_data in list(layer.items()):
                px, py = pos
                if x <= px < x + width and y <= py < y + height:
                    rel_x = px - x
                    rel_y = py - y
                    y_positions.append(rel_y)
                    sprites_to_move.append((layer_enum, pos, block_data.copy(), rel_x, rel_y))
                    positions_to_clear.append((layer_enum, pos))
        
        if not sprites_to_move:
            return
        
        # Step 2: Find the Y range of the current sprites
        min_y = min(y_positions)
        max_y = max(y_positions)
        
        # Step 3: Clear all original positions
        for layer_enum, pos in positions_to_clear:
            if pos in self.layers[layer_enum]:
                del self.layers[layer_enum][pos]
        
        # Step 4: Place sprites flipped around the center of their current range
        affected_positions = []
        for layer_enum, original_pos, block_data, rel_x, rel_y in sprites_to_move:
            # Flip within the sprite arrangement's own range
            flipped_rel_y = max_y - (rel_y - min_y)
            new_pos = (x + rel_x, y + flipped_rel_y)
            
            if self.is_valid_position(new_pos[0], new_pos[1]) and not self.is_bedrock_position(new_pos[1]):
                self.layers[layer_enum][new_pos] = block_data
                affected_positions.append(new_pos)
        
        # Step 5: Update chunks
        if affected_positions:
            self.chunk_manager.force_update_affected_chunks(affected_positions)
            self.force_immediate_chunk_update()

    def paste_selection(self, target_x, target_y):
        """Paste clipboard at target position using bottom-left as origin with collision detection"""
        if not self.clipboard:
            return
    
        # Find the bounds of the clipboard selection
        all_positions = []
        for layer_dict in self.clipboard.values():
            all_positions.extend(layer_dict.keys())
        
        if not all_positions:
            return
        
        # Find the bottom-left corner of the selection
        min_rel_x = min(rel_x for rel_x, rel_y in all_positions)
        max_rel_y = max(rel_y for rel_x, rel_y in all_positions)
        
        affected_positions = []
        
        for layer_enum, layer_dict in self.clipboard.items():
            for rel_pos, block_data in layer_dict.items():
                rel_x, rel_y = rel_pos
                # Place relative to bottom-left corner
                world_x = target_x + (rel_x - min_rel_x)
                world_y = target_y - (max_rel_y - rel_y)
    
                if (self.is_valid_position(world_x, world_y) and 
                    not self.is_bedrock_position(world_y)):
                    
                    # Check for collision before placing
                    if not self.tile_renderer.check_placement_collision(self, world_x, world_y, block_data, layer_enum):
                        self.layers[layer_enum][(world_x, world_y)] = block_data.copy()
                        affected_positions.append((world_x, world_y))
        
        # Clear selection after pasting
        if self.selection:
            self.selection = None
            self.selection_start = None
            self.init_ui()
        
        # Force immediate chunk updates for all affected positions
        if affected_positions:
            self.chunk_manager.force_update_affected_chunks(affected_positions)
            self.force_immediate_chunk_update()

    def flood_fill(self, start_x, start_y, target_block, replacement_block):
        """Ultra-optimized flood fill with batched operations"""
        if not self.is_valid_position(start_x, start_y):
            return
        if self.is_bedrock_position(start_y):
            return
    
        if target_block is not None and replacement_block is not None:
            if target_block.get('id', '') == replacement_block.get('id', ''):
                return
    
        # Calculate sprite dimensions once
        if replacement_block is not None:
            sprite = self.block_manager.get_sprite(replacement_block['id'])
            if sprite:
                tile_mode = replacement_block.get('tileMode', 'standard')
                bounds = self.tile_renderer.calculate_sprite_bounds(sprite, tile_mode)
                
                if bounds:
                    min_x = min(dx for dx, dy in bounds)
                    max_x = max(dx for dx, dy in bounds)
                    min_y = min(dy for dx, dy in bounds)
                    max_y = max(dy for dx, dy in bounds)
                    
                    grid_width = max_x - min_x + 1
                    grid_height = max_y - min_y + 1
                    offset_x = -min_x
                    offset_y = -min_y
                else:
                    grid_width, grid_height = 1, 1
                    offset_x, offset_y = 0, 0
            else:
                grid_width, grid_height = 1, 1
                offset_x, offset_y = 0, 0
        else:
            grid_width, grid_height = 1, 1
            offset_x, offset_y = 0, 0
    
        # Find grid origin
        world_min_x = 0
        world_max_y = self.world_height - self.bedrock_rows
        grid_origin_x = (world_min_x // grid_width) * grid_width
        grid_origin_y = (world_max_y // grid_height) * grid_height
    
        print(f"Starting flood fill: sprite {grid_width}x{grid_height}")
    
        # STEP 1: Fast flood fill to find all matching tiles (no sprite placement yet)
        matching_tiles = set()
        stack = [(start_x, start_y)]
        visited = set()
        
        while stack:
            x, y = stack.pop()
            if (x, y) in visited:
                continue
    
            if not self.is_valid_position(x, y) or self.is_bedrock_position(y):
                continue
    
            visited.add((x, y))
            current_block = self.layers[self.active_layer].get((x, y), None)
    
            # Check if matches target
            matches_target = False
            if target_block is None and current_block is None:
                matches_target = True
            elif (target_block is not None and current_block is not None and
                target_block.get('id', '') == current_block.get('id', '')):
                matches_target = True
    
            if matches_target:
                matching_tiles.add((x, y))
                
                # Continue flood fill
                for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                    next_x, next_y = x + dx, y + dy
                    if (next_x, next_y) not in visited:
                        stack.append((next_x, next_y))
    
        print(f"Found {len(matching_tiles)} matching tiles")
    
        if replacement_block is not None:
            # STEP 2: Calculate all valid grid positions (batch calculation)
            grid_positions = set()
            
            for x, y in matching_tiles:
                grid_x = ((x - grid_origin_x) // grid_width) * grid_width + grid_origin_x
                grid_y = ((y - grid_origin_y) // grid_height) * grid_height + grid_origin_y
                
                sprite_x = grid_x + offset_x
                sprite_y = grid_y + offset_y
                
                if (self.is_valid_position(sprite_x, sprite_y) and 
                    not self.is_bedrock_position(sprite_y)):
                    grid_positions.add((sprite_x, sprite_y))
    
            print(f"Calculated {len(grid_positions)} sprite positions")
    
            # STEP 3: Batch collision checking (pre-filter invalid positions)
            valid_positions = []
            layer_dict = self.layers[self.active_layer]
            
            for sprite_x, sprite_y in grid_positions:
                # Only check if origin position is free and not in bedrock
                if ((sprite_x, sprite_y) not in layer_dict and 
                    not self.is_bedrock_position(sprite_y)):
                    valid_positions.append((sprite_x, sprite_y))
                
            print(f"Validated {len(valid_positions)} positions for placement")
    
            # STEP 4: Batch placement (single operation)
            block_copy = replacement_block.copy()
            
            # Disable chunk invalidation temporarily
            old_invalidate = self.chunk_manager.invalidate_chunk
            self.chunk_manager.invalidate_chunk = lambda x, y: None
            
            # Place all sprites in one batch
            for sprite_x, sprite_y in valid_positions:
                self.layers[self.active_layer][(sprite_x, sprite_y)] = block_copy.copy()
            
            # Restore chunk invalidation
            self.chunk_manager.invalidate_chunk = old_invalidate
            
            print(f"Placed {len(valid_positions)} sprites")
            
        else:
            # STEP 4: Batch erase mode - FIXED: Extra bedrock protection
            layer_dict = self.layers[self.active_layer]
            positions_to_remove = []
            
            for x, y in matching_tiles:
                # FIXED: Double-check bedrock protection for erase mode
                if (x, y) in layer_dict and not self.is_bedrock_position(y):
                    positions_to_remove.append((x, y))
            
            # Batch remove
            for pos in positions_to_remove:
                del layer_dict[pos]
            
            print(f"Erased {len(positions_to_remove)} tiles")
    
        # STEP 5: Single chunk invalidation at the end
        self.chunk_manager.invalidate_all_chunks()
        print("Flood fill complete!")
    
    def flood_fill_async(self, start_x, start_y, target_block, replacement_block):
        """Async version that doesn't freeze the UI (optional)"""
        import threading
        
        def run_flood_fill():
            self.flood_fill(start_x, start_y, target_block, replacement_block)
            # Force a UI refresh after completion
            pygame.event.post(pygame.event.Event(pygame.USEREVENT, {'flood_fill_complete': True}))
        
        thread = threading.Thread(target=run_flood_fill)
        thread.daemon = True
        thread.start()

    def handle_key_press(self, key):
        """Handle keyboard shortcuts with optimizations"""
        if self.is_searching:
            self.handle_search_input(key)
            return
        
        if self.is_inputting_brush_size:
            self.handle_brush_size_input(key)
            return
    
        previous_tool = self.active_tool
    
        # Tool shortcuts
        tool_map = {
            pygame.K_p: Tool.PLACE,
            pygame.K_b: Tool.BRUSH,
            pygame.K_f: Tool.FILL,
            pygame.K_e: Tool.ERASE,
            pygame.K_s: Tool.SELECT,
            pygame.K_v: Tool.PASTE,
            pygame.K_i: Tool.EYEDROPPER
        }
        
        if key in tool_map:
            # Store previous tool if switching away from place or brush
            if self.active_tool in [Tool.PLACE, Tool.BRUSH]:
                self.previous_tool = self.active_tool
            self.active_tool = tool_map[key]
        
        # Clear selection if tool changed and new tool is not SELECT
        if previous_tool != self.active_tool and self.active_tool != Tool.SELECT:
            self.selection = None
            self.selection_start = None
        
        # Layer shortcuts
        if key == pygame.K_1:
            self.set_active_layer(Layer.BACKGROUND)
        elif key == pygame.K_2:
            self.set_active_layer(Layer.MIDGROUND)
        
        # Undo/Redo
        elif key == pygame.K_z and pygame.key.get_mods() & pygame.KMOD_CTRL:
            self.undo()
        elif key == pygame.K_y and pygame.key.get_mods() & pygame.KMOD_CTRL:
            self.redo()
        
        # Copy/Paste
        elif key == pygame.K_c and pygame.key.get_mods() & pygame.KMOD_CTRL:
            if self.selection:
                self.copy_selection()
        
        # Toggle settings
        elif key == pygame.K_g:
            self.toggle_grid()
        elif key == pygame.K_b and pygame.key.get_mods() & pygame.KMOD_CTRL:
            self.toggle_borders()
        
        # Brush size
        elif key == pygame.K_PLUS or key == pygame.K_EQUALS:
            if self.active_tool in [Tool.BRUSH, Tool.ERASE]:
                self.set_brush_size(min(self.brush_size + 1, 50))
        elif key == pygame.K_MINUS:
            if self.active_tool in [Tool.BRUSH, Tool.ERASE]:
                self.set_brush_size(max(self.brush_size - 1, 1))
        
        # Escape
        elif key == pygame.K_ESCAPE:
            self.selection = None
            self.selection_start = None
        
        # Search
        elif key == pygame.K_f and pygame.key.get_mods() & pygame.KMOD_CTRL:
            self.activate_search()
        
        # Toggle hotkey help
        elif key == pygame.K_F1:
            self.hotkey_help.toggle_visibility()
        
        # Debug sprite occupancy
        elif key == pygame.K_F2:
            if self.selected_block:
                self.debug_sprite_occupancy(self.selected_block['id'])
        
        # Multi-state block controls
        elif key == pygame.K_LEFT and pygame.key.get_mods() & pygame.KMOD_SHIFT:
            if self.selected_block and 'state' in self.selected_block:
                self.cycle_block_state(self.selected_block, -1)
        elif key == pygame.K_RIGHT and pygame.key.get_mods() & pygame.KMOD_SHIFT:
            if self.selected_block and 'state' in self.selected_block:
                self.cycle_block_state(self.selected_block, 1)

        # Update tool button states
        for t, b in self.toolbuttons.items():
            b['active'] = (t == self.active_tool)

        self.init_ui()

    def handle_search_input(self, key):
        """Handle keyboard input for the search bar"""
        if key == pygame.K_BACKSPACE:
            if len(self.search_text) > 0 and self.search_cursor_pos > 0:
                self.search_text = self.search_text[:self.search_cursor_pos - 1] + self.search_text[self.search_cursor_pos:]
                self.search_cursor_pos -= 1
        elif key == pygame.K_DELETE:
            if self.search_cursor_pos < len(self.search_text):
                self.search_text = self.search_text[:self.search_cursor_pos] + self.search_text[self.search_cursor_pos + 1:]
        elif key == pygame.K_LEFT:
            self.search_cursor_pos = max(0, self.search_cursor_pos - 1)
        elif key == pygame.K_RIGHT:
            self.search_cursor_pos = min(len(self.search_text), self.search_cursor_pos + 1)
        elif key == pygame.K_RETURN or key == pygame.K_ESCAPE:
            self.is_searching = False
            self.init_ui()
        else:
            try:
                if 32 <= key <= 126:
                    char = chr(key)
                    self.search_text = self.search_text[:self.search_cursor_pos] + char + self.search_text[self.search_cursor_pos:]
                    self.search_cursor_pos += 1
            except ValueError:
                pass

        if 'search_bar' in self.buttons:
            self.buttons['search_bar']['text'] = f"Search: {self.search_text}"

        self.init_ui()

    def handle_brush_size_input(self, key):
        """Handle keyboard input for custom brush size"""
        if key == pygame.K_BACKSPACE:
            if len(self.custom_brush_text) > 0 and self.custom_brush_cursor_pos > 0:
                self.custom_brush_text = self.custom_brush_text[:self.custom_brush_cursor_pos - 1] + self.custom_brush_text[self.custom_brush_cursor_pos:]
                self.custom_brush_cursor_pos -= 1
        elif key == pygame.K_DELETE:
            if self.custom_brush_cursor_pos < len(self.custom_brush_text):
                self.custom_brush_text = self.custom_brush_text[:self.custom_brush_cursor_pos] + self.custom_brush_text[self.custom_brush_cursor_pos + 1:]
        elif key == pygame.K_LEFT:
            self.custom_brush_cursor_pos = max(0, self.custom_brush_cursor_pos - 1)
        elif key == pygame.K_RIGHT:
            self.custom_brush_cursor_pos = min(len(self.custom_brush_text), self.custom_brush_cursor_pos + 1)
        elif key == pygame.K_RETURN:
            # Apply the custom brush size
            try:
                size = int(self.custom_brush_text) if self.custom_brush_text else 1
                size = max(1, min(50, size))  # Clamp between 1 and 50
                self.set_brush_size(size)
            except ValueError:
                pass  # Invalid input, ignore
            self.is_inputting_brush_size = False
            self.init_ui()
        elif key == pygame.K_ESCAPE:
            self.is_inputting_brush_size = False
            self.init_ui()
        else:
            # Only allow digits
            try:
                if 48 <= key <= 57:  # 0-9 keys
                    char = chr(key)
                    # Prevent input if it would exceed 2 digits or result in >50
                    new_text = self.custom_brush_text[:self.custom_brush_cursor_pos] + char + self.custom_brush_text[self.custom_brush_cursor_pos:]
                    if len(new_text) <= 2:
                        try:
                            if int(new_text) <= 50:
                                self.custom_brush_text = new_text
                                self.custom_brush_cursor_pos += 1
                        except ValueError:
                            pass
            except ValueError:
                pass

        # Update button text
        if 'brush_size_custom' in self.buttons:
            self.buttons['brush_size_custom']['text'] = f"Custom: {self.custom_brush_text}"

    def cycle_block_state(self, block, direction=1):
        """Cycle through available states for a multi-state block"""
        if 'state' in block and 'stateCount' in block:
            current_state = block.get('state', 0)
            state_count = block.get('stateCount', 2)
            
            if direction > 0:
                new_state = (current_state + 1) % state_count
            else:
                new_state = (current_state - 1) % state_count
            
            block['state'] = new_state
            self.init_ui()

    def undo(self):
        """Undo last action"""
        restored_layers = self.undo_manager.undo()
        if restored_layers is not None:
            self.layers = restored_layers
            self.chunk_manager.invalidate_all_chunks()
            self.init_ui()

    def redo(self):
        """Redo previously undone action"""
        restored_layers = self.undo_manager.redo()
        if restored_layers is not None:
            self.layers = restored_layers
            self.chunk_manager.invalidate_all_chunks()
            self.init_ui()

    def handle_mouse_motion(self, pos):
        """Handle mouse motion with optimizations and coordinate tracking"""
        # Handle tooltip updates
        self.handle_toolbar_hover(pos)
        
        # Efficient coordinate calculation for grid display
        if self.canvas_rect.collidepoint(pos):
            effective_tile_size = self.tile_size * self.zoom
            canvas_x = pos[0] - self.toolbar_width - self.resize_handle_width
            
            # Convert to world grid coordinates
            world_tile_x = int((canvas_x + self.camera_x) / effective_tile_size)
            world_tile_y = int((pos[1] + self.camera_y) / effective_tile_size)
            
            # Convert to user coordinates (0,0 at bottom-left excluding bedrock)
            if self.is_valid_position(world_tile_x, world_tile_y):
                self.mouse_grid_x = world_tile_x
                # Flip Y coordinate: 0 at bottom (excluding bedrock)
                usable_height = self.world_height - self.bedrock_rows
                self.mouse_grid_y = (usable_height - 1) - world_tile_y
                # Clamp to valid range
                self.mouse_grid_y = max(0, self.mouse_grid_y)
        
        # Handle scrollbar dragging
        if self.is_dragging_scrollbar:
            self.handle_scrollbar_drag(pos)
            return
        
        # Handle toolbar resizing
        if self.is_resizing_toolbar:
            new_width = pos[0]
            self.toolbar_width = max(self.min_toolbar_width, min(self.max_toolbar_width, new_width))
    
            self.canvas_rect = pygame.Rect(
                self.toolbar_width + self.resize_handle_width, 0,
                self.screen_width - self.toolbar_width - self.resize_handle_width,
                self.screen_height
            )
    
            self.init_ui()
            return
    
        if self.is_dragging:
            # Pan camera with infinite panning support
            mouse_x, mouse_y = pos
            last_x, last_y = self.last_mouse_pos
    
            delta_x = last_x - mouse_x
            delta_y = last_y - mouse_y
            
            self.camera_x += delta_x
            self.camera_y += delta_y
    
            # Check for mouse wrapping during panning
            wrap_margin = 50  # Distance from edge to trigger wrap
            new_mouse_x, new_mouse_y = mouse_x, mouse_y
            wrapped = False
    
            # Wrap horizontally
            if mouse_x <= wrap_margin:
                new_mouse_x = self.screen_width - wrap_margin - 1
                wrapped = True
            elif mouse_x >= self.screen_width - wrap_margin:
                new_mouse_x = wrap_margin + 1
                wrapped = True
    
            # Wrap vertically
            if mouse_y <= wrap_margin:
                new_mouse_y = self.screen_height - wrap_margin - 1
                wrapped = True
            elif mouse_y >= self.screen_height - wrap_margin:
                new_mouse_y = wrap_margin + 1
                wrapped = True
    
            # Apply wrapping if needed
            if wrapped:
                pygame.mouse.set_pos(new_mouse_x, new_mouse_y)
                self.last_mouse_pos = (new_mouse_x, new_mouse_y)
            else:
                self.last_mouse_pos = pos
    
        # Update cursor
        if self.is_point_on_resize_handle(pos):
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_SIZEWE)
        else:
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
    
        # Handle brush painting while dragging
        if pygame.mouse.get_pressed()[0] and self.canvas_rect.collidepoint(pos):
            if self.active_tool in [Tool.BRUSH, Tool.ERASE]:
                effective_tile_size = self.tile_size * self.zoom
                canvas_x = pos[0] - self.toolbar_width - self.resize_handle_width
                tile_x = int((canvas_x + self.camera_x) / effective_tile_size)  # Ensure same as preview
                tile_y = int((pos[1] + self.camera_y) / effective_tile_size)    # Ensure same as preview
    
                if self.is_valid_position(tile_x, tile_y):
                    if self.active_tool == Tool.BRUSH and self.selected_block:
                        block_data = self.create_block_data_from_selected()
                        if block_data:
                            self.place_blocks_with_brush(tile_x, tile_y, block_data)
                    elif self.active_tool == Tool.ERASE:
                        self.erase_blocks_with_brush(tile_x, tile_y)

    def place_blocks_with_brush(self, center_x, center_y, block_data):
        """Optimized brush placement using pre-calculated patterns"""
        self.brush_manager.add_brush_position(center_x, center_y, is_erase=False)
        
        # Update chunks if enough time has passed
        if self.brush_manager.should_update_chunks():
            self.brush_manager.finish_brush_stroke()
    
    def erase_blocks_with_brush(self, center_x, center_y):
        """Optimized brush erasure using pre-calculated patterns"""
        self.brush_manager.add_brush_position(center_x, center_y, is_erase=True)
        
        # Update chunks if enough time has passed
        if self.brush_manager.should_update_chunks():
            self.brush_manager.finish_brush_stroke()

    def force_immediate_chunk_update(self):
        """Force immediate chunk rendering that works at all zoom levels"""
        # Clear any zoom-related caches that might interfere
        current_zoom = self.tile_size * self.zoom
        
        # Force chunks to be marked as needing re-render if zoom changed
        if self.chunk_manager.cached_zoom != self.zoom:
            self.chunk_manager.cached_zoom = self.zoom
        
        # Temporarily increase chunk render limit for immediate updates
        old_limit = self.chunk_manager.max_chunks_per_frame
        self.chunk_manager.max_chunks_per_frame = 50  # Higher limit for immediate updates
        
        try:
            # Force visible chunks to render at current zoom
            effective_tile_size = int(self.tile_size * self.zoom)
            self.chunk_manager.force_render_visible_chunks(
                int(self.camera_x), int(self.camera_y), effective_tile_size
            )
        finally:
            # Always restore original limit
            self.chunk_manager.max_chunks_per_frame = old_limit

    def is_point_on_resize_handle(self, pos):
        """Check if a point is on the resize handle"""
        return (self.toolbar_width <= pos[0] <= self.toolbar_width + self.resize_handle_width and
                0 <= pos[1] <= self.screen_height)

    def handle_mouse_up(self, pos, button):
        """Handle mouse button up events with optimizations"""
        if button == 1:
            if self.is_dragging_scrollbar:
                self.is_dragging_scrollbar = False
                return
                
            if self.is_resizing_toolbar:
                self.is_resizing_toolbar = False
            elif self.active_tool == Tool.SELECT and self.selection_start:
                self.handle_selection(self.selection_start, pos)
                self.selection_start = None
                self.copy_selection()
            elif self.batch_operation_active:
                self.end_batch_operation()
            
            # OPTIMIZED: Finish brush stroke on mouse up
            if self.active_tool in [Tool.BRUSH, Tool.ERASE]:
                self.brush_manager.finish_brush_stroke(force=True)
    
        elif button == 3:
            if self.is_dragging:
                self.is_dragging = False
                # Release mouse capture when panning ends
                pygame.event.set_grab(False)

    def handle_mouse_wheel(self, event):
        """Handle mouse wheel events with optimizations"""
        mouse_pos = pygame.mouse.get_pos()
        keys = pygame.key.get_pressed()
        ctrl_pressed = keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]
        shift_pressed = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
    
        if mouse_pos[0] < self.toolbar_width:
            # Scroll toolbar
            self.toolbar_scroll_y = max(0, min(self.toolbar_max_scroll,
                                            self.toolbar_scroll_y - event.y * 30))
    
        elif self.canvas_rect.collidepoint(mouse_pos):
            scroll_speed = max(20, int(30 * self.zoom))
    
            if ctrl_pressed:
                # OPTIMIZED ZOOM - Only invalidate chunks on significant zoom changes
                canvas_x = mouse_pos[0] - self.toolbar_width - self.resize_handle_width
                canvas_y = mouse_pos[1]
    
                old_effective_tile_size = self.tile_size * self.zoom
                world_x = (canvas_x + self.camera_x) / old_effective_tile_size
                world_y = (canvas_y + self.camera_y) / old_effective_tile_size
    
                old_zoom = self.zoom
    
                if event.y > 0:
                    self.zoom = min(self.zoom + 0.125, 5.0)
                else:
                    self.zoom = max(self.zoom - 0.125, 0.125)
    
                if old_zoom != self.zoom:
                    new_effective_tile_size = self.tile_size * self.zoom
    
                    self.camera_x = world_x * new_effective_tile_size - canvas_x
                    self.camera_y = world_y * new_effective_tile_size - canvas_y
    
                    self.camera_x = round(self.camera_x)
                    self.camera_y = round(self.camera_y)
                    
                    # OPTIMIZED: Only clear caches and invalidate on significant zoom changes
                    zoom_change = abs(old_zoom - self.zoom)
                    if zoom_change >= 0.25 or self.chunk_manager.cached_zoom != self.zoom:
                        self.background_manager.clear_background_cache()
                        self.chunk_manager.invalidate_all_chunks()
                        self.chunk_manager.cached_zoom = self.zoom
    
            elif shift_pressed:
                # Shift+Wheel = Horizontal scrolling
                self.camera_x += -event.y * scroll_speed
                self.camera_x = round(self.camera_x)
    
            else:
                # Regular vertical scrolling
                self.camera_y += -event.y * scroll_speed
                self.camera_y = round(self.camera_y)

    def handle_window_resize(self, event):
        """Handle window resize events with optimizations"""
        self.screen_width = event.w
        self.screen_height = event.h
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height), pygame.RESIZABLE)

        self.canvas_rect = pygame.Rect(
            self.toolbar_width + self.resize_handle_width, 0,
            self.screen_width - self.toolbar_width - self.resize_handle_width,
            self.screen_height
        )

        # Clear caches on resize
        self.background_manager.clear_background_cache()
        self.ui_surface_cache.clear()

        self.init_ui()
        self.hotkey_help.mark_dirty()
        self.hotkey_help.update_help()

    def run_optimized(self):
        """Optimized main application loop with comprehensive performance monitoring"""
        print("🚀 Starting optimized main loop...")
        
        # Initialize update manager 
        try:
            self.update_manager = UpdateManager(APP_VERSION)
            self.update_manager.check_for_updates()
            self.last_update_state = False
            print("✅ Update manager initialized")
        except Exception as e:
            print(f"⚠️ Update manager failed to initialize: {e}")
            self.update_manager = None
            self.last_update_state = False
        
        while self.running:
            frame_start_time = pygame.time.get_ticks()
            
            # Check for update status changes and refresh UI if needed
            if (self.update_manager and 
                self.update_manager.check_complete and 
                self.update_manager.update_available != self.last_update_state):
                self.last_update_state = self.update_manager.update_available
                if self.update_manager.update_available:
                    print(f"🔄 Update detected, refreshing UI...")
                    self.init_ui()
            
            # Handle events with batching
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self.selection or self.selection_start:
                            self.selection = None
                            self.selection_start = None
                        else:
                            self.running = False
                    else:
                        self.handle_key_press(event.key)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self.handle_mouse_click(event.pos, event.button)
                elif event.type == pygame.MOUSEBUTTONUP:
                    self.handle_mouse_up(event.pos, event.button)
                elif event.type == pygame.MOUSEMOTION:
                    self.handle_mouse_motion(event.pos)
                elif event.type == pygame.MOUSEWHEEL:
                    self.handle_mouse_wheel(event)
                elif event.type == pygame.VIDEORESIZE:
                    self.handle_window_resize(event)
            
            # Handle autosave timer
            if self.autosave_directory:
                self.autosave_timer += self.clock.get_time()
                if self.autosave_timer >= self.autosave_interval:
                    self.perform_autosave()
                    self.autosave_timer = 0
            
            # UPDATE TOOLTIPS EVEN WITHOUT MOUSE MOVEMENT
            mouse_pos = pygame.mouse.get_pos()
            self.handle_toolbar_hover(mouse_pos)  # This will check tooltip timing
            
            # Adaptive performance management
            current_time = pygame.time.get_ticks()
            if self.adaptive_chunk_rendering and (current_time - self.last_frame_time) > self.frame_skip_threshold:
                # Reduce chunk rendering load
                self.chunk_manager.max_chunks_per_frame = max(1, self.chunk_manager.max_chunks_per_frame - 1)
                self.performance_stats['adaptive_quality'] *= 0.95
            else:
                # Gradually increase chunk rendering when performance is good
                self.chunk_manager.max_chunks_per_frame = min(5, self.chunk_manager.max_chunks_per_frame + 1)
                self.performance_stats['adaptive_quality'] = min(1.0, self.performance_stats['adaptive_quality'] * 1.01)
            
            # Clear screen efficiently
            self.screen.fill((17, 17, 17))
            
            # Render everything with optimizations
            self.render_world_optimized(self.screen)
            self.draw_toolbar(self.screen)
            
            # Draw UI overlays
            self.tooltip_manager.draw(self.screen, self.screen_width, self.screen_height)
            self.hotkey_help.draw(self.screen, self.screen_width, self.toolbar_width, self.resize_handle_width)
            
            # Performance monitoring and stats
            self.frame_count += 1
            self.last_frame_time = current_time
            frame_time = current_time - frame_start_time
            self.performance_stats['frame_time'] = frame_time
            
            # Print performance stats every 5 seconds
            if current_time - self.performance_timer > 5000:
                avg_fps = self.frame_count / 5.0
                self.performance_stats['fps'] = avg_fps
                
                print(f"🔥 Performance: {avg_fps:.1f} FPS | "
                    f"Frame: {frame_time}ms | "
                    f"Render: {self.performance_stats['render_time']}ms | "
                    f"Chunks/frame: {self.chunk_manager.max_chunks_per_frame} | "
                    f"Quality: {self.performance_stats['adaptive_quality']:.2f}")
                
                # Print cache stats
                print(f"📊 Cache Stats: {self.tooltip_manager.get_cache_stats()}")
                print(f"🖼️ Background Cache: {self.background_manager.cache_hits}/{self.background_manager.cache_hits + self.background_manager.cache_misses} hits")
                
                self.frame_count = 0
                self.performance_timer = current_time
            
            # Update display with VSync if available
            pygame.display.flip()
            self.clock.tick(60)  # Target 60 FPS
        
        # Perform final autosave on exit
        if self.autosave_directory:
            print("Performing final autosave before exit...")
            self.perform_autosave()
        
        print("🛑 Shutting down optimized World Planner...")
        print(f"📈 Final Performance Stats:")
        print(f"   • Average FPS: {self.performance_stats['fps']:.1f}")
        print(f"   • Tooltip Cache Hit Rate: {self.tooltip_manager.cache_hits}/{self.tooltip_manager.cache_hits + self.tooltip_manager.cache_misses}")
        print(f"   • Background Cache Hit Rate: {self.background_manager.cache_hits}/{self.background_manager.cache_hits + self.background_manager.cache_misses}")
        print(f"   • UI Surface Cache Size: {len(self.ui_surface_cache)}")
        
        pygame.quit()

    def fix_chunk_grid_rendering(self):
        """HOTFIX: Override broken grid rendering in OptimizedChunk"""
        def draw_chunk_grid_optimized_fixed(chunk_self, world_planner, base_tile_size, expanded_size, has_world_background):
            """Fixed grid drawing method"""
            if has_world_background:
                grid_color = (120, 120, 120, 180)
            else:
                grid_color = (70, 70, 70)
            
            # Calculate world boundaries
            start_tile_x = chunk_self.x * chunk_self.size - chunk_self.border
            start_tile_y = chunk_self.y * chunk_self.size - chunk_self.border
            world_width = world_planner.world_width
            world_height = world_planner.world_height
            
            # Draw vertical lines (FIXED: Draw each line individually)
            for local_x in range(expanded_size + 1):
                world_x = start_tile_x + local_x
                if 0 <= world_x < world_width:
                    x_pos = local_x * base_tile_size
                    y_start = max(0, (-start_tile_y) * base_tile_size)
                    y_end = min(expanded_size * base_tile_size, (world_height - start_tile_y) * base_tile_size)
                    if y_end > y_start:
                        pygame.draw.line(chunk_self.surface, grid_color, (x_pos, y_start), (x_pos, y_end), 1)
            
            # Draw horizontal lines (FIXED: Draw each line individually)
            for local_y in range(expanded_size + 1):
                world_y = start_tile_y + local_y
                if 0 <= world_y < world_height:
                    y_pos = local_y * base_tile_size
                    x_start = max(0, (-start_tile_x) * base_tile_size)
                    x_end = min(expanded_size * base_tile_size, (world_width - start_tile_x) * base_tile_size)
                    if x_end > x_start:
                        pygame.draw.line(chunk_self.surface, grid_color, (x_start, y_pos), (x_end, y_pos), 1)
        
        # Replace the broken method in all OptimizedChunk instances
        import types
        from chunk_manager import OptimizedChunk
        OptimizedChunk.draw_chunk_grid_optimized = draw_chunk_grid_optimized_fixed
        print("🔧 Applied grid rendering hotfix")


def main():
    """Main function with comprehensive optimization"""
    print("🌟 Initializing Optimized World Planner...")
    
    # Set pygame optimization environment variables
    os.environ['SDL_VIDEO_CENTERED'] = '1'  # Center window
    os.environ['SDL_VIDEO_WINDOW_POS'] = '100,100'  # Set window position
    
    # Additional performance hints
    if hasattr(os, 'environ'):
        os.environ['SDL_HINT_RENDER_SCALE_QUALITY'] = '1'  # Linear filtering
        os.environ['SDL_HINT_ACCELERATED_VIDEO'] = '1'  # Try hardware acceleration
    
    try:
        # Create and run optimized planner
        planner = OptimizedWorldPlanner()
        planner.run_optimized()
    except Exception as e:
        print(f"❌ Error running World Planner: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("👋 World Planner session ended.")


if __name__ == "__main__":
    main()
