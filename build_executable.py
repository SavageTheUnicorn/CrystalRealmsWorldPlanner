#!/usr/bin/env python3
"""
Fixed build script for World Planner that creates a 100% standalone executable
Now includes proper BackgroundManager embedding support and OptimizedBrushManager
"""

import os
import sys
import base64
import json
import shutil
import subprocess
from pathlib import Path
import tempfile

def check_pyinstaller():
    """Check if PyInstaller is properly installed and working"""
    try:
        result = subprocess.run([sys.executable, '-m', 'PyInstaller', '--version'], 
                              capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"✅ PyInstaller version: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ PyInstaller check failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ PyInstaller check timed out")
        return False
    except FileNotFoundError:
        print("❌ PyInstaller not found in PATH")
        return False
    except Exception as e:
        print(f"❌ PyInstaller check error: {e}")
        return False

def create_embedded_resources():
    """Create a Python file with all resources embedded as base64/JSON data"""
    
    sprites_data = {}
    backgrounds_data = {}
    
    # Scan spritesSORTED directory
    sprites_sorted_dir = Path("spritesSORTED")
    if sprites_sorted_dir.exists():
        for sprite_file in sprites_sorted_dir.rglob("*.png"):
            try:
                with open(sprite_file, 'rb') as f:
                    sprite_data = base64.b64encode(f.read()).decode('utf-8')
                
                # Use forward slashes and relative path as key
                relative_path = str(sprite_file.relative_to(sprites_sorted_dir)).replace('\\', '/')
                sprites_data[relative_path] = sprite_data
                print(f"Embedded sprite: {relative_path}")
            except Exception as e:
                print(f"Error embedding {sprite_file}: {e}")
    
    # Scan worldbgs directory - FIXED: Store separately for backgrounds
    worldbgs_dir = Path("worldbgs")
    if worldbgs_dir.exists():
        for bg_file in worldbgs_dir.rglob("*.png"):
            try:
                with open(bg_file, 'rb') as f:
                    bg_data = base64.b64encode(f.read()).decode('utf-8')
                
                # Store background metadata for BackgroundManager
                relative_path = str(bg_file.relative_to(worldbgs_dir)).replace('\\', '/')
                filename = bg_file.name
                base_name = bg_file.stem
                bg_name = base_name.replace('_', ' ').replace('-', ' ').title()
                
                backgrounds_data[relative_path] = {
                    'data': bg_data,
                    'filename': filename,
                    'name': bg_name,
                    'id': base_name.lower()
                }
                print(f"Embedded background: {relative_path} -> {bg_name}")
            except Exception as e:
                print(f"Error embedding {bg_file}: {e}")
    
    # Scan additional backgrounds directory
    backgrounds_dir = Path("backgrounds")
    if backgrounds_dir.exists():
        for bg_file in backgrounds_dir.rglob("*.png"):
            try:
                with open(bg_file, 'rb') as f:
                    bg_data = base64.b64encode(f.read()).decode('utf-8')
                
                relative_path = f"backgrounds/{str(bg_file.relative_to(backgrounds_dir)).replace(chr(92), '/')}"
                filename = bg_file.name
                base_name = bg_file.stem
                bg_name = base_name.replace('_', ' ').replace('-', ' ').title()
                
                backgrounds_data[relative_path] = {
                    'data': bg_data,
                    'filename': filename,
                    'name': bg_name,
                    'id': base_name.lower()
                }
                print(f"Embedded background: {relative_path} -> {bg_name}")
            except Exception as e:
                print(f"Error embedding {bg_file}: {e}")
    
    # EMBED TILE RULES - This is the key fix!
    tile_rules_data = {}
    if os.path.exists('tile_rules.json'):
        try:
            with open('tile_rules.json', 'r', encoding='utf-8') as f:
                tile_rules_data = json.load(f)
            print("✅ Embedded tile_rules.json")
        except Exception as e:
            print(f"❌ Error embedding tile_rules.json: {e}")
            # Use default rules if file doesn't exist
            tile_rules_data = get_default_tile_rules()
    else:
        print("⚠️ tile_rules.json not found, using defaults")
        tile_rules_data = get_default_tile_rules()
    
    # Create embedded_resources.py with EVERYTHING embedded
    embedded_code = '''"""
Embedded resources for World Planner - 100% Standalone Version
Auto-generated by build_executable.py
"""

import base64
import io
import json
import pygame
from typing import Dict, Optional

# All sprites embedded as base64 data
EMBEDDED_SPRITES = ''' + json.dumps(sprites_data, indent=2) + '''

# All backgrounds embedded as base64 data with metadata
EMBEDDED_BACKGROUNDS = ''' + json.dumps(backgrounds_data, indent=2) + '''

# Tile rules embedded as JSON data
EMBEDDED_TILE_RULES = ''' + json.dumps(tile_rules_data, indent=2) + '''

def get_sprite(relative_path: str) -> Optional[pygame.Surface]:
    """Load a sprite from embedded data"""
    try:
        if relative_path in EMBEDDED_SPRITES:
            sprite_data = base64.b64decode(EMBEDDED_SPRITES[relative_path])
            sprite_bytes = io.BytesIO(sprite_data)
            surface = pygame.image.load(sprite_bytes)
            return surface.convert_alpha()
        else:
            print(f"Warning: Sprite not found: {relative_path}")
            return None
    except Exception as e:
        print(f"Error loading embedded sprite {relative_path}: {e}")
        return None

def get_background(relative_path: str) -> Optional[pygame.Surface]:
    """Load a background from embedded data"""
    try:
        if relative_path in EMBEDDED_BACKGROUNDS:
            bg_data = base64.b64decode(EMBEDDED_BACKGROUNDS[relative_path]['data'])
            bg_bytes = io.BytesIO(bg_data)
            surface = pygame.image.load(bg_bytes)
            return surface.convert()
        else:
            print(f"Warning: Background not found: {relative_path}")
            return None
    except Exception as e:
        print(f"Error loading embedded background {relative_path}: {e}")
        return None

def get_background_list() -> list:
    """Get list of all available backgrounds with metadata"""
    bg_list = []
    
    # Add "None" option first
    bg_list.append({
        'id': 'none',
        'name': 'None',
        'surface': None,
        'path': None
    })
    
    # Add embedded backgrounds
    for relative_path, bg_info in EMBEDDED_BACKGROUNDS.items():
        bg_list.append({
            'id': bg_info['id'],
            'name': bg_info['name'],
            'surface': None,  # Will be loaded on demand
            'path': relative_path
        })
    
    return bg_list

def get_tile_rules() -> dict:
    """Get embedded tile rules"""
    return EMBEDDED_TILE_RULES.copy()

def get_all_sprite_paths() -> list:
    """Get all available sprite paths"""
    return list(EMBEDDED_SPRITES.keys())

def get_all_background_paths() -> list:
    """Get all available background paths"""
    return list(EMBEDDED_BACKGROUNDS.keys())

def sprite_exists(relative_path: str) -> bool:
    """Check if a sprite exists in embedded data"""
    return relative_path in EMBEDDED_SPRITES

def background_exists(relative_path: str) -> bool:
    """Check if a background exists in embedded data"""
    return relative_path in EMBEDDED_BACKGROUNDS

# Debug function
def debug_resources():
    """Print debug info about embedded resources"""
    print(f"Total embedded sprites: {len(EMBEDDED_SPRITES)}")
    for path in sorted(EMBEDDED_SPRITES.keys())[:10]:
        print(f"  - {path}")
    if len(EMBEDDED_SPRITES) > 10:
        print(f"  ... and {len(EMBEDDED_SPRITES) - 10} more")
    
    print(f"Total embedded backgrounds: {len(EMBEDDED_BACKGROUNDS)}")
    for path in sorted(EMBEDDED_BACKGROUNDS.keys()):
        bg_info = EMBEDDED_BACKGROUNDS[path]
        print(f"  - {path} -> {bg_info['name']} (ID: {bg_info['id']})")
    
    print(f"Tile rules keys: {list(EMBEDDED_TILE_RULES.keys())}")
'''
    
    try:
        with open('embedded_resources.py', 'w', encoding='utf-8') as f:
            f.write(embedded_code)
        
        # Validate the created file
        print("Validating embedded_resources.py...")
        with open('embedded_resources.py', 'r', encoding='utf-8') as f:
            content = f.read()
            if ('EMBEDDED_SPRITES' in content and 'EMBEDDED_BACKGROUNDS' in content and 
                'EMBEDDED_TILE_RULES' in content and len(content) > 1000):
                print("✅ embedded_resources.py created and validated")
            else:
                print("❌ embedded_resources.py seems incomplete")
                return False
        
    except Exception as e:
        print(f"❌ Error creating embedded_resources.py: {e}")
        return False
    
    print(f"Created embedded_resources.py with {len(sprites_data)} sprites, {len(backgrounds_data)} backgrounds, and tile rules")
    return len(sprites_data) + len(backgrounds_data)

def get_default_tile_rules():
    """Default tile rules if file is missing"""
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
            "background_quadrant": {
                "type": "background_quadrant",
                "connects_to": ["self"],
                "sprite_layout": {
                    "quadrant": {"x": 0, "y": 0, "width": 16, "height": 16}
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
        },
        "directory_mappings": {
            "spritesSORTED/connectables/bgs": "background_quadrant"
        },
        "sprite_detection_patterns": {
            "vine_patterns": ["vine", "ivy"],
            "cactus_patterns": ["cactus"],
            "platform_patterns": ["platform"],
            "fence_patterns": ["fence"],
            "connected_block_patterns": ["dirt", "stone", "wood"],
            "background_quadrant_patterns": ["bg", "background"]
        }
    }

def create_embedded_background_manager():
    """Create embedded version of BackgroundManager"""
    
    background_manager_code = '''import os
import pygame

# Import embedded resources
try:
    import embedded_resources
    EMBEDDED_MODE = True
    print("✅ BackgroundManager: Using embedded background resources")
except ImportError:
    EMBEDDED_MODE = False
    print("Warning: embedded_resources not found in BackgroundManager, falling back to file system")


class OptimizedBackgroundManager:
    """Optimized background manager with advanced caching and performance improvements - Embedded Version"""
    
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
    
    def load_backgrounds(self):
        """Load all background images from embedded resources or file system"""
        if EMBEDDED_MODE:
            self.load_embedded_backgrounds()
        else:
            self.load_file_system_backgrounds()
    
    def load_embedded_backgrounds(self):
        """Load backgrounds from embedded resources"""
        try:
            # Add "None" option first
            self.background_list.append({
                'id': 'none',
                'name': 'None',
                'surface': None,
                'path': None
            })
            
            # Add embedded backgrounds
            embedded_bgs = embedded_resources.EMBEDDED_BACKGROUNDS
            print(f"Found {len(embedded_bgs)} embedded backgrounds")
            
            for relative_path, bg_info in embedded_bgs.items():
                bg_entry = {
                    'id': bg_info['id'],
                    'name': bg_info['name'],
                    'surface': None,  # Will be loaded on demand
                    'path': relative_path
                }
                self.background_list.append(bg_entry)
                self.backgrounds[bg_info['id']] = bg_entry
                print(f"✅ Registered embedded background: {bg_info['name']} (ID: {bg_info['id']})")
            
            # Set default background to first actual background (not "none")
            if len(self.background_list) > 1:
                self.current_background = self.background_list[1]['id']
                print(f"✅ Set default background to: {self.backgrounds[self.current_background]['name']}")
            else:
                self.current_background = 'none'
                print("⚠️ No embedded backgrounds found, using 'None'")
            
        except Exception as e:
            print(f"❌ Error loading embedded backgrounds: {e}")
            self.fallback_to_none()
    
    def load_file_system_backgrounds(self):
        """Fallback to file system loading"""
        bg_dirs = self.get_background_directories()
        
        if not bg_dirs:
            print("Warning: No background directories found!")
            self.fallback_to_none()
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
        
        print(f"Loaded {loaded_count} background images from file system")
        
        if len(self.background_list) > 1:
            self.current_background = self.background_list[1]['id']
        else:
            self.current_background = 'none'
    
    def fallback_to_none(self):
        """Fallback when no backgrounds are available"""
        self.background_list = [{
            'id': 'none',
            'name': 'None',
            'surface': None,
            'path': None
        }]
        self.backgrounds = {'none': self.background_list[0]}
        self.current_background = 'none'
    
    def get_background_directories(self):
        """Get directories containing background images (file system fallback)"""
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
    
    def load_background_file(self, bg_path):
        """Load a single background file (file system fallback)"""
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
            
            bg_surface = pygame.image.load(bg_path).convert()
            
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
        
        bg_info = self.backgrounds[self.current_background]
        
        # Load surface on demand if using embedded resources
        if EMBEDDED_MODE and bg_info.get('surface') is None and bg_info.get('path'):
            try:
                print(f"Loading embedded background surface: {bg_info['path']}")
                bg_info['surface'] = embedded_resources.get_background(bg_info['path'])
                if bg_info['surface']:
                    print(f"✅ Successfully loaded embedded background: {bg_info['name']}")
                else:
                    print(f"❌ Failed to load embedded background: {bg_info['name']}")
                    return None
            except Exception as e:
                print(f"❌ Error loading embedded background surface {bg_info['path']}: {e}")
                return None
        
        bg_surface = bg_info.get('surface')
        if not bg_surface:
            return None
        
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
                scaled_bg = pygame.transform.smoothscale(bg_surface, target_size)
                scaled_bg = scaled_bg.convert()
        except:
            scaled_bg = pygame.transform.scale(bg_surface, target_size)
            scaled_bg = scaled_bg.convert()
        
        # Cache management
        if len(self.scaled_background_cache) > 15:
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
                self.clear_background_cache()
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
'''
    
    try:
        with open('background_manager_embedded.py', 'w', encoding='utf-8') as f:
            f.write(background_manager_code)
        
        print("✅ Created background_manager_embedded.py")
        return True
    except Exception as e:
        print(f"❌ Error creating background_manager_embedded.py: {e}")
        return False

def create_modified_block_manager():
    """Create a modified block_manager.py that uses embedded resources"""
    
    block_manager_code = '''import os
import sys
import json
import pygame
from pathlib import Path

# Import embedded resources
try:
    import embedded_resources
    EMBEDDED_MODE = True
    print("Using embedded sprite resources")
except ImportError:
    EMBEDDED_MODE = False
    print("Warning: embedded_resources not found, falling back to file system")


class BlockManager:
    """Manages block definitions and sprite loading"""
    
    def __init__(self):
        self.blocks = {}
        self.sprites = {}
        self.sprite_paths = {}
        self.custom_blocks = []
        
        # Initialize default blocks
        self.init_default_blocks()
        
        # Load tile rules for sprite type detection
        self.tile_rules = self.load_tile_rules()
    
    def load_tile_rules(self):
        """Load tile rules from embedded resources or file system"""
        if EMBEDDED_MODE:
            try:
                rules = embedded_resources.get_tile_rules()
                print("✅ Loaded tile rules from embedded resources")
                return rules
            except Exception as e:
                print(f"Error loading embedded tile rules: {e}")
                return self.get_default_tile_rules()
        else:
            # Fallback to file system
            try:
                if os.path.exists('tile_rules.json'):
                    with open('tile_rules.json', 'r') as f:
                        return json.load(f)
                else:
                    print("Warning: tile_rules.json not found, using minimal defaults")
                    return self.get_default_tile_rules()
            except Exception as e:
                print(f"Error loading tile rules: {e}")
                return self.get_default_tile_rules()
    
    def get_default_tile_rules(self):
        """Get default tile rules if embedded resources fail"""
        return {
            "directory_mappings": {},
            "sprite_detection_patterns": {
                "vine_patterns": ["vine", "ivy"],
                "cactus_patterns": ["cactus"],
                "platform_patterns": ["platform"],
                "fence_patterns": ["fence"],
                "connected_block_patterns": ["dirt", "stone", "wood"]
            }
        }
    
    def init_default_blocks(self):
        """Initialize default block definitions"""
        self.blocks = {
            'terrain': [
                {
                    'id': 'dirt',
                    'name': 'Dirt Block',
                    'color': (139, 69, 19),
                    'category': 'terrain',
                    'tileSet': True,
                    'tileMode': 'all',
                    'tileable': {'top': True, 'right': True, 'bottom': True, 'left': True}
                },
                {
                    'id': 'grass',
                    'name': 'Grass Block',
                    'color': (86, 125, 70),
                    'category': 'terrain',
                    'tileSet': True,
                    'tileMode': 'all',
                    'tileable': {'top': False, 'right': True, 'bottom': True, 'left': True}
                },
                {
                    'id': 'stone',
                    'name': 'Stone Block',
                    'color': (128, 128, 128),
                    'category': 'terrain',
                    'tileSet': True,
                    'tileMode': 'all',
                    'tileable': {'top': True, 'right': True, 'bottom': True, 'left': True}
                },
                {
                    'id': 'wood',
                    'name': 'Wood Block',
                    'color': (139, 90, 43),
                    'category': 'terrain',
                    'tileSet': True,
                    'tileMode': 'log',
                    'tileable': {'top': True, 'right': True, 'bottom': True, 'left': True}
                },
                {
                    'id': 'obsidian',
                    'name': 'Obsidian Block',
                    'color': (33, 11, 44),
                    'category': 'terrain',
                    'tileSet': True,
                    'tileMode': 'all',
                    'tileable': {'top': True, 'right': True, 'bottom': True, 'left': True}
                }
            ],
            'decorative': [
                {
                    'id': 'vine',
                    'name': 'Vine',
                    'color': (0, 255, 0),
                    'category': 'decorative',
                    'tileSet': True,
                    'tileMode': 'vine',
                    'tileable': {'top': True, 'right': False, 'bottom': True, 'left': False}
                },
                {
                    'id': 'cactus',
                    'name': 'Cactus',
                    'color': (0, 200, 0),
                    'category': 'decorative',
                    'tileSet': True,
                    'tileMode': 'vertical',
                    'tileable': {'top': True, 'right': False, 'bottom': True, 'left': False}
                }
            ],
            'interactive': [
                {
                    'id': 'platform',
                    'name': 'Platform',
                    'color': (222, 184, 135),
                    'category': 'interactive',
                    'tileSet': True,
                    'tileMode': 'platform_enhanced',
                    'tileable': {'top': False, 'right': True, 'bottom': False, 'left': True}
                }
            ],
            'custom': []
        }
    
    def detect_sprite_type_from_path(self, file_path):
        """Detect sprite type from file path using directory structure"""
        # Normalize path separators
        norm_path = file_path.replace('\\\\', '/')
        path_parts = norm_path.split('/')
        
        # Handle embedded resource paths
        if len(path_parts) > 0:
            first_part = path_parts[0]
            
            if first_part == '1state':
                return 'standard'
            elif first_part == '2state':
                return '2state'
            elif first_part == '4state':
                return '4state'
            elif first_part == 'connectables' and len(path_parts) > 1:
                sub_category = path_parts[1]
                if sub_category == 'blocks':
                    return 'all'
                elif sub_category == 'logs':
                    return 'log'
                elif sub_category == 'platforms':
                    return 'platform_enhanced'
                elif sub_category == 'fences':
                    return 'fence_enhanced'
                elif sub_category == 'bedrockandwater':
                    return 'bedrock_pattern'
                elif sub_category == 'buttonblocks':
                    return 'standard'
                elif sub_category == 'smallerblocks':
                    return 'smaller_blocks'
                elif sub_category == 'chain':
                    return 'chain'
                elif sub_category == 'columns':
                    return 'column'
                elif sub_category == 'bgs':
                    return 'background_quadrant'
                elif sub_category == 'greenery' and len(path_parts) > 2:
                    greenery_type = path_parts[2]
                    if greenery_type == 'down':
                        return 'vine'
                    elif greenery_type == 'up':
                        return 'vertical'
                return 'standard'
        
        # Check filename for patterns
        filename = file_path.lower()
        if 'vine' in filename or 'ivy' in filename:
            return 'vine'
        elif 'cactus' in filename or 'bamboo' in filename:
            return 'vertical'
        
        return 'standard'
    
    def load_sprites(self):
        """Load all sprites from embedded resources or file system"""
        loaded_count = 0
        
        if EMBEDDED_MODE:
            # Load from embedded resources
            sprite_paths = embedded_resources.get_all_sprite_paths()
            print(f"Loading {len(sprite_paths)} sprites from embedded resources...")
            
            for sprite_path in sprite_paths:
                if self.load_sprite_from_embedded(sprite_path):
                    loaded_count += 1
        else:
            # Fallback to file system loading
            print("Loading sprites from file system...")
            sprite_dirs = self.get_sprite_directories()
            for sprite_dir in sprite_dirs:
                sprite_files = self.scan_directory_for_sprites(sprite_dir)
                for sprite_path in sprite_files:
                    if self.load_sprite_file(sprite_path):
                        loaded_count += 1
        
        print(f"Loaded {loaded_count} sprites total")
        
        # Update custom blocks
        self.update_custom_blocks()
    
    def load_sprite_from_embedded(self, sprite_path):
        """Load a sprite from embedded resources"""
        try:
            # Generate block ID from path
            path_parts = sprite_path.split('/')
            filename = path_parts[-1]
            base_name = os.path.splitext(filename)[0]
            
            # Create unique ID
            if len(path_parts) > 1:
                parent_dir = path_parts[-2]
                block_id = f"{parent_dir}_{base_name}".lower()
            else:
                block_id = base_name.lower()
            
            # Clean up the ID
            block_id = ''.join(c if c.isalnum() or c == '_' else '_' for c in block_id)
            
            # Ensure uniqueness
            original_id = block_id
            counter = 1
            while block_id in self.sprites:
                block_id = f"{original_id}_{counter}"
                counter += 1
            
            # Load the sprite from embedded data
            sprite = embedded_resources.get_sprite(sprite_path)
            if sprite:
                self.sprites[block_id] = sprite
                self.sprite_paths[block_id] = sprite_path
                return True
            
            return False
            
        except Exception as e:
            print(f"Error loading embedded sprite {sprite_path}: {e}")
            return False
    
    def get_sprite_directories(self):
        """Get sprite directories for file system fallback"""
        dirs = []
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # FIXED: Exclude worldbgs directory - backgrounds are handled separately by BackgroundManager
        # Only include actual sprite directories, not background directories
        for dir_name in ["spritesSORTED", "sprites"]:  # Removed "worldbgs"
            dir_path = os.path.join(base_dir, dir_name)
            if os.path.exists(dir_path):
                dirs.append(dir_path)
        
        return dirs
    
    def scan_directory_for_sprites(self, directory):
        """Recursively scan directory for sprite files"""
        sprite_files = []
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                    sprite_files.append(os.path.join(root, file))
        return sprite_files
    
    def load_sprite_file(self, sprite_path):
        """Load sprite from file system"""
        try:
            sprite = pygame.image.load(sprite_path).convert_alpha()
            filename = os.path.basename(sprite_path)
            base_name = os.path.splitext(filename)[0]
            
            # Generate unique ID
            block_id = base_name.lower()
            original_id = block_id
            counter = 1
            while block_id in self.sprites:
                block_id = f"{original_id}_{counter}"
                counter += 1
            
            self.sprites[block_id] = sprite
            self.sprite_paths[block_id] = sprite_path
            return True
            
        except Exception as e:
            print(f"Error loading sprite {sprite_path}: {e}")
            return False
    
    def update_custom_blocks(self):
        """Update the custom blocks category with loaded sprites"""
        self.blocks['custom'] = []
        
        # Get existing block IDs to avoid duplicates
        existing_ids = set()
        for category, blocks in self.blocks.items():
            if category != 'custom':
                for block in blocks:
                    existing_ids.add(block['id'])
        
        # Create blocks for custom sprites
        for block_id, sprite_path in self.sprite_paths.items():
            if block_id not in existing_ids:
                sprite_type = self.detect_sprite_type_from_path(sprite_path)
                
                block_def = {
                    'id': block_id,
                    'name': self.create_friendly_name(block_id),
                    'color': (200, 200, 200),
                    'category': 'custom',
                    'custom': True,
                    'tileSet': sprite_type != 'standard',
                    'tileMode': sprite_type
                }
                
                # Add state information for multi-state blocks
                if sprite_type == '2state':
                    block_def['state'] = 0
                    block_def['stateCount'] = 2
                elif sprite_type == '4state':
                    block_def['state'] = 0
                    block_def['stateCount'] = 4
                
                # Add tileable properties
                if sprite_type == 'vine':
                    block_def['tileable'] = {'top': True, 'right': False, 'bottom': True, 'left': False}
                elif sprite_type == 'vertical':
                    block_def['tileable'] = {'top': True, 'right': False, 'bottom': True, 'left': False}
                elif sprite_type == 'chain':
                    block_def['tileable'] = {'top': True, 'right': False, 'bottom': True, 'left': False}
                elif sprite_type == 'column':
                    block_def['tileable'] = {'top': True, 'right': False, 'bottom': True, 'left': False}
                elif sprite_type == 'platform_enhanced':
                    block_def['tileable'] = {'top': False, 'right': True, 'bottom': False, 'left': True}
                elif sprite_type == 'fence_enhanced':
                    block_def['tileable'] = {'top': False, 'right': True, 'bottom': False, 'left': True}
                elif sprite_type == 'background_quadrant':
                    block_def['tileable'] = {'top': True, 'right': True, 'bottom': True, 'left': True}
                elif sprite_type in ['all', 'smaller_blocks', 'bedrock_pattern']:
                    block_def['tileable'] = {'top': True, 'right': True, 'bottom': True, 'left': True}
                else:
                    block_def['tileable'] = {'top': False, 'right': False, 'bottom': False, 'left': False}
                
                self.blocks['custom'].append(block_def)
        
        # Sort custom blocks by name
        self.blocks['custom'].sort(key=lambda x: x['name'])
        
        print(f"Created {len(self.blocks['custom'])} custom blocks")
    
    def create_friendly_name(self, block_id):
        """Create a user-friendly name from block ID"""
        name = block_id
        
        # Remove common prefixes
        prefixes = ['custom_', 'sprite_', 'tile_']
        for prefix in prefixes:
            if name.startswith(prefix):
                name = name[len(prefix):]
        
        # Split on underscores and capitalize
        parts = name.split('_')
        friendly_parts = []
        
        for part in parts:
            if part and not part.isdigit():
                friendly_parts.append(part.capitalize())
        
        return ' '.join(friendly_parts) if friendly_parts else block_id.capitalize()
    
    def get_sprite(self, block_id):
        """Get sprite for a block ID"""
        return self.sprites.get(block_id, None)
    
    def get_block_by_id(self, block_id):
        """Get block definition by ID"""
        for category, blocks in self.blocks.items():
            for block in blocks:
                if block['id'] == block_id:
                    return block
        return None
    
    def get_blocks_by_category(self, category):
        """Get all blocks in a category"""
        return self.blocks.get(category, [])
    
    def get_all_categories(self):
        """Get all block categories"""
        return list(self.blocks.keys())
    
    def add_custom_block(self, block_id, sprite_path, block_name=None):
        """Add a custom block with sprite"""
        if EMBEDDED_MODE:
            print("Custom block addition disabled in embedded version")
            return False
        return self.load_sprite_file(sprite_path)
    
    def debug_sprite_info(self, block_id):
        """Print debug information about a sprite"""
        sprite = self.get_sprite(block_id)
        block = self.get_block_by_id(block_id)
        sprite_path = self.sprite_paths.get(block_id, "Unknown")
        
        print(f"\\n=== DEBUG INFO: {block_id} ===")
        print(f"Sprite exists: {sprite is not None}")
        if sprite:
            print(f"Sprite size: {sprite.get_width()}x{sprite.get_height()}")
        print(f"Sprite path: {sprite_path}")
        print(f"Block definition: {block}")
        if block:
            print(f"Tile mode: {block.get('tileMode', 'standard')}")
            print(f"Tile set: {block.get('tileSet', False)}")
        print("=" * 50)
'''
    
    try:
        with open('block_manager_embedded.py', 'w', encoding='utf-8') as f:
            f.write(block_manager_code)
        
        print("✅ Created block_manager_embedded.py")
        return True
    except Exception as e:
        print(f"❌ Error creating block_manager_embedded.py: {e}")
        return False

def create_modified_main():
    """Create a modified main.py that imports the embedded managers"""
    
    try:
        # Read the original main.py
        with open('main.py', 'r', encoding='utf-8') as f:
            main_content = f.read()
        
        # Replace the import statements
        main_content = main_content.replace(
            'from block_manager import BlockManager',
            'from block_manager_embedded import BlockManager'
        )
        
        # Replace the OptimizedBackgroundManager class definition with an import
        # Find the class definition and replace it
        import_replacement = '''
# Import embedded BackgroundManager
try:
    from background_manager_embedded import OptimizedBackgroundManager as EmbeddedBackgroundManager
    USE_EMBEDDED_BG = True
    print("✅ Using embedded OptimizedBackgroundManager")
except ImportError:
    USE_EMBEDDED_BG = False
    print("⚠️ Could not import embedded OptimizedBackgroundManager, using inline version")
'''
        
        # Insert at the top after imports
        import_index = main_content.find('from constants import')
        if import_index != -1:
            import_end = main_content.find('\n\n', import_index)
            if import_end != -1:
                main_content = (main_content[:import_end] + 
                              import_replacement + 
                              main_content[import_end:])
        
        # Replace the background manager initialization
        old_init = "self.background_manager = OptimizedBackgroundManager()"
        new_init = """if USE_EMBEDDED_BG:
            self.background_manager = EmbeddedBackgroundManager()
        else:
            self.background_manager = OptimizedBackgroundManager()"""
        
        main_content = main_content.replace(old_init, new_init)
        
        with open('main_embedded.py', 'w', encoding='utf-8') as f:
            f.write(main_content)
        
        print("✅ Created main_embedded.py with proper background manager integration")
        return True
    except Exception as e:
        print(f"❌ Error creating main_embedded.py: {e}")
        return False

def validate_generated_files():
    """Validate that all generated files are correct"""
    required_files = [
        'embedded_resources.py',
        'block_manager_embedded.py', 
        'background_manager_embedded.py',
        'main_embedded.py'
    ]
    
    print("Validating generated files...")
    for file in required_files:
        if not os.path.exists(file):
            print(f"❌ Missing file: {file}")
            return False
        
        try:
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read()
                if len(content) < 100:  # Basic size check
                    print(f"❌ File too small: {file}")
                    return False
            print(f"✅ {file} validated")
        except Exception as e:
            print(f"❌ Error reading {file}: {e}")
            return False
    
    return True

def create_standalone_spec_file():
    """Create a PyInstaller spec file for 100% standalone executable"""
    spec_content = """# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

# Analysis of the main script
a = Analysis(
    ['main_embedded.py'],
    pathex=[],
    binaries=[],
    datas=[
        # NO EXTERNAL FILES - everything is embedded in Python code
    ],
    hiddenimports=[
        'pygame',
        'pygame.freetype',
        'pygame.math',
        'tkinter',
        'tkinter.filedialog',
        'json',
        'base64',
        'io',
        'typing',
        'pathlib',
        'math',
        'os',
        'sys',
        'copy',
        'threading',
        'embedded_resources',
        'undo_manager',
        'block_manager_embedded',
        'background_manager_embedded',
        'constants',
        'tile_renderer',
        'chunk_manager'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Create the PYZ archive
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Create the executable - ONE FILE, NO EXTERNAL DEPENDENCIES
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='WorldPlanner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if Path('icon.ico').exists() else None,
    # CRITICAL: These options ensure 100% standalone
    onefile=True,  # Force single file
    windowed=True,  # No console window
)
"""
    
    try:
        with open("worldplanner_standalone.spec", "w", encoding="utf-8") as f:
            f.write(spec_content)
        print("✅ Created standalone PyInstaller spec file")
        return True
    except Exception as e:
        print(f"❌ Error creating spec file: {e}")
        return False

def build_standalone_executable():
    """Build using the standalone spec file"""
    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "worldplanner_standalone.spec"]

    print(f"Building standalone executable with command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=os.getcwd(),
            capture_output=False,
            text=True,
            timeout=600  # 10 minutes timeout
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("❌ Build timed out after 10 minutes")
        return False
    except Exception as e:
        print(f"❌ Build error: {e}")
        return False

def install_requirements():
    """Install required packages"""
    requirements = [
        'pygame>=2.0.0', 
        'pyinstaller>=5.0',
        'setuptools',
        'wheel'
    ]
    
    for req in requirements:
        try:
            print(f"Installing {req}...")
            result = subprocess.run([sys.executable, '-m', 'pip', 'install', req], 
                                  capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                print(f"✅ Installed {req}")
            else:
                print(f"❌ Failed to install {req}: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ Error installing {req}: {e}")
            return False
    
    return True

def cleanup_temp_files():
    """Clean up temporary files created during build"""
    temp_files = [
        'embedded_resources.py',
        'block_manager_embedded.py',
        'background_manager_embedded.py',
        'main_embedded.py',
        'worldplanner_standalone.spec'
    ]
    
    temp_dirs = [
        'build',
        '__pycache__'
    ]
    
    print("Cleaning up temporary files...")
    for file in temp_files:
        if os.path.exists(file):
            try:
                os.remove(file)
                print(f"✅ Removed {file}")
            except Exception as e:
                print(f"❌ Failed to remove {file}: {e}")
    
    for dir in temp_dirs:
        if os.path.exists(dir):
            try:
                shutil.rmtree(dir)
                print(f"✅ Removed {dir}/")
            except Exception as e:
                print(f"❌ Failed to remove {dir}/: {e}")

def verify_standalone_executable():
    """Verify that the executable is truly standalone"""
    exe_path = None
    
    # Check for executable
    if os.path.exists('dist/WorldPlanner.exe'):
        exe_path = 'dist/WorldPlanner.exe'
    elif os.path.exists('dist/WorldPlanner'):
        exe_path = 'dist/WorldPlanner'
    
    if not exe_path:
        print("❌ No executable found in dist/ folder")
        return False
    
    # Check file size
    size_mb = os.path.getsize(exe_path) / (1024 * 1024)
    print(f"✅ Executable created: {exe_path} ({size_mb:.1f} MB)")
    
    # Check for _internal folder (should NOT exist for standalone)
    internal_path = os.path.join(os.path.dirname(exe_path), '_internal')
    if os.path.exists(internal_path):
        print(f"⚠️ WARNING: {internal_path} folder exists - executable is NOT standalone!")
        print("The executable will need the _internal folder to run properly.")
        return False
    else:
        print("✅ No _internal folder found - executable is truly standalone!")
        return True

def main():
    """Main build process for 100% standalone executable"""
    print("=== World Planner 100% Standalone Build Script ===")
    print("Now with full BackgroundManager support and OptimizedBrushManager!")
    print()
    
    # Check for required files
    required_files = ['main.py', 'tile_renderer.py', 'chunk_manager.py', 'constants.py', 'block_manager.py', 'undo_manager.py']
    missing_files = [f for f in required_files if not os.path.exists(f)]
    
    if missing_files:
        print(f"❌ Missing required files: {', '.join(missing_files)}")
        return False
    
    try:
        # Step 1: Install requirements
        print("Step 1: Installing requirements...")
        if not install_requirements():
            print("❌ Failed to install requirements")
            return False
        
        # Step 2: Check PyInstaller
        print("\nStep 2: Checking PyInstaller...")
        if not check_pyinstaller():
            print("❌ PyInstaller not working properly")
            return False
        
        # Step 3: Create embedded resources (including backgrounds and tile rules)
        print("\nStep 3: Creating embedded resources...")
        resource_count = create_embedded_resources()
        if resource_count is False:
            print("❌ Failed to create embedded resources")
            return False
        
        # Step 4: Create modified files
        print("\nStep 4: Creating modified source files...")
        if not create_modified_block_manager():
            return False
        if not create_embedded_background_manager():  # NEW: Create embedded background manager
            return False
        if not create_modified_main():
            return False
        
        # Step 5: Validate generated files
        print("\nStep 5: Validating generated files...")
        if not validate_generated_files():
            print("❌ Generated files validation failed")
            return False
        
        # Step 6: Create standalone spec file
        print("\nStep 6: Creating standalone PyInstaller spec...")
        if not create_standalone_spec_file():
            print("❌ Failed to create spec file")
            return False
        
        # Step 7: Build executable
        print("\nStep 7: Building standalone executable...")
        print("This may take several minutes...")
        if build_standalone_executable():
            print("\n🎉 Build completed!")
            
            # Step 8: Verify standalone nature
            print("\nStep 8: Verifying standalone executable...")
            if verify_standalone_executable():
                print("\n🎉 SUCCESS: 100% Standalone executable created!")
                print(f"📊 Embedded {resource_count} total resources (sprites + backgrounds + tile rules)")
                print("\n📋 Your friends can now:")
                print("   1. Download just the .exe file")
                print("   2. Run it anywhere without any other files")
                print("   3. No Python installation required")
                print("   4. No _internal folder needed")
                print("   5. Full background support included!")
                print("   6. Optimized brush performance included!")
            else:
                print("\n⚠️ Build completed but executable may not be fully standalone")
                return False
        else:
            print("❌ Build failed!")
            return False
        
        # Step 9: Cleanup (optional)
        print("\nStep 9: Cleaning up temporary files...")
        cleanup_temp_files()
        
        return True
        
    except KeyboardInterrupt:
        print("\n⚠️ Build interrupted by user")
        return False
    except Exception as e:
        print(f"\n❌ Build process failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 Build completed successfully!")
        print("\n📦 Distribution Instructions:")
        print("1. Share ONLY the WorldPlanner.exe file (no folders needed)")
        print("2. Recipients can run it on any Windows machine")
        print("3. No Python, dependencies, or additional files required")
        print("4. 100% standalone - works anywhere!")
        print("5. All backgrounds and sprites included!")
        print("6. Optimized brush performance included!")
    else:
        print("\n❌ Build failed. Please check the errors above.")
    
    input("\nPress Enter to exit...")
