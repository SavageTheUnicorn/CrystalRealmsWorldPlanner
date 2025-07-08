import os
import sys
import json
import pygame
from pathlib import Path


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
        """Load tile rules for sprite type detection"""
        try:
            with open('tile_rules.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print("Warning: tile_rules.json not found, using minimal defaults")
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
        except Exception as e:
            print(f"Error loading tile rules: {e}")
            return {}
    
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
                    'tileMode': 'all',  # Use 'all' for complex tiling like original
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
                    'tileMode': 'log',  # Special log tiling
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
                    'tileMode': 'vertical',  # Use 'vertical' like original
                    'tileable': {'top': True, 'right': False, 'bottom': True, 'left': False}
                },
                {
                    'id': 'flower_red',
                    'name': 'Red Flower',
                    'color': (255, 0, 0),
                    'category': 'decorative',
                    'tileSet': False,
                    'tileMode': 'standard'
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
                },
                {
                    'id': 'fence',
                    'name': 'Fence',
                    'color': (160, 82, 45),
                    'category': 'interactive',
                    'tileSet': True,
                    'tileMode': 'fence_enhanced',
                    'tileable': {'top': False, 'right': True, 'bottom': False, 'left': True}
                }
            ],
            'custom': []
        }
    
    def get_sprite_directories(self):
        """Get all sprite directories to scan"""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        dirs = []
        
        # Check for spritesSORTED directory (priority)
        sprites_sorted_dir = os.path.join(base_dir, "spritesSORTED")
        if os.path.exists(sprites_sorted_dir):
            dirs.append(sprites_sorted_dir)
        
        # REMOVED: worldbgs directory - backgrounds are handled separately by BackgroundManager
        # worldbgs_dir = os.path.join(base_dir, "worldbgs")
        # if os.path.exists(worldbgs_dir):
        #     dirs.append(worldbgs_dir)
        
        # Check for original sprites directory
        sprites_dir = os.path.join(base_dir, "sprites")
        if os.path.exists(sprites_dir):
            dirs.append(sprites_dir)
        
        # Check for user sprites directory
        user_sprites_dir = os.path.join(os.path.expanduser("~"), ".worldplanner", "sprites")
        if os.path.exists(user_sprites_dir):
            dirs.append(user_sprites_dir)
        
        return dirs
    
    def detect_sprite_type_from_path(self, file_path):
        """Detect sprite type from file path using directory structure - IMPROVED DETECTION"""
        norm_path = os.path.normpath(file_path).replace('\\', '/')
        path_parts = norm_path.split('/')
        
        # Check for spritesSORTED directory structure
        if 'spritesSORTED' in path_parts:
            sorted_index = path_parts.index('spritesSORTED')
            
            # Need at least one subdirectory after spritesSORTED
            if len(path_parts) > sorted_index + 1:
                top_category = path_parts[sorted_index + 1]
                
                # 1state directory - always use standard tiling
                if top_category == '1state':
                    return 'standard'
                
                # 2state directory - use special 2-state rendering
                elif top_category == '2state':
                    return '2state'
                
                # 4state directory - use special 4-state rendering
                elif top_category == '4state':
                    return '4state'
                
                # connectables subdirectories - EXACT MATCH TO DIRECTORY STRUCTURE
                elif top_category == 'connectables':
                    # Check for connectables subdirectories
                    if len(path_parts) > sorted_index + 2:
                        sub_category = path_parts[sorted_index + 2]
                        
                        # Each specific subdirectory gets its own tiling mode
                        if sub_category == 'blocks':
                            return 'all'  # Complex 47-tile autotiling for terrain blocks
                        elif sub_category == 'logs':
                            return 'log'  # Special log tiling (2 tiles wide)
                        elif sub_category == 'platforms':
                            return 'platform_enhanced'  # Enhanced horizontal platform mode
                        elif sub_category == 'fences':
                            return 'fence_enhanced'  # Enhanced horizontal fence mode
                        elif sub_category == 'bedrockandwater':
                            return 'bedrock_pattern'  # Simple alternating pattern mode
                        elif sub_category == 'buttonblocks':
                            return 'standard'  # Standard single-sprite rendering
                        elif sub_category == 'smallerblocks':
                            return 'smaller_blocks'  # Quadrant-based smaller blocks mode
                        elif sub_category == 'chain':
                            return 'chain'  # Chain tiling mode
                        elif sub_category == 'bgs':
                            return 'background_quadrant'  # NEW: Background quadrant tiling
                        elif sub_category == 'columns':
                            return 'column'  # NEW: Column tiling mode
                        elif sub_category == 'greenery':
                            # Check for greenery subdirectories
                            if len(path_parts) > sorted_index + 3:
                                greenery_type = path_parts[sorted_index + 3]
                                if greenery_type == 'down':
                                    return 'vine'  # Hanging downward vines
                                elif greenery_type == 'up':
                                    return 'vertical'  # Growing upward (cactus-like)
                            return 'standard'  # Default for other greenery
                    
                    # Default for connectables without a specific subdirectory
                    return 'standard'
        
        # Check for worldbgs directory (background sprites)
        if 'worldbgs' in path_parts:
            return 'standard'  # Background sprites are typically standard
        
        # Check filename for specific patterns
        filename = os.path.basename(file_path).lower()
        
        # Vine-like sprites
        if any(pattern in filename for pattern in ['vine', 'ivy', 'creeper', 'hanging', 'tendril']):
            return 'vine'
        
        # Cactus-like sprites (vertical growth)
        elif any(pattern in filename for pattern in ['cactus', 'bamboo', 'reed']):
            return 'vertical'
        
        # Platform sprites
        elif any(pattern in filename for pattern in ['platform', 'ledge', 'bridge']):
            return 'platform_enhanced'
        
        # Fence sprites
        elif any(pattern in filename for pattern in ['fence', 'gate', 'rail', 'barrier']):
            return 'fence_enhanced'
        
        # Connected block patterns (terrain that should use complex tiling)
        elif any(pattern in filename for pattern in ['dirt', 'stone', 'wood', 'brick', 'grass', 'sand']):
            return 'all'
        
        # Default to standard tiling if no special pattern is detected
        return 'standard'
    
    def scan_directory_for_sprites(self, directory):
        """Recursively scan directory for sprite files"""
        sprite_files = []
        
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                    full_path = os.path.join(root, file)
                    sprite_files.append(full_path)
        
        return sprite_files
    
    def load_sprites(self):
        """Load all sprites from sprite directories"""
        sprite_dirs = self.get_sprite_directories()
        
        if not sprite_dirs:
            print("Warning: No sprite directories found!")
            return
        
        loaded_count = 0
        
        for sprite_dir in sprite_dirs:
            print(f"Loading sprites from: {sprite_dir}")
            sprite_files = self.scan_directory_for_sprites(sprite_dir)
            
            for sprite_path in sprite_files:
                if self.load_sprite_file(sprite_path):
                    loaded_count += 1
        
        print(f"Loaded {loaded_count} sprites total")
        
        # Update custom blocks
        self.update_custom_blocks()
    
    def load_sprite_file(self, sprite_path):
        """Load a single sprite file"""
        try:
            # Generate block ID from filename and path
            filename = os.path.basename(sprite_path)
            base_name = os.path.splitext(filename)[0]
            
            # Create unique ID including path info to avoid conflicts
            relative_path = os.path.relpath(sprite_path)
            path_parts = relative_path.replace('\\', '/').split('/')
            
            # Create a more unique ID
            if len(path_parts) > 2:
                # Include parent directory in ID for uniqueness
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
            
            # Load the sprite
            sprite = pygame.image.load(sprite_path).convert_alpha()
            
            self.sprites[block_id] = sprite
            self.sprite_paths[block_id] = sprite_path
            
            print(f"Loaded sprite: {block_id} from {sprite_path}")
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
                # Detect sprite type using the IMPROVED detection method
                sprite_type = self.detect_sprite_type_from_path(sprite_path)
                
                # Create block definition with proper category
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
                
                # Add tileable properties based on sprite type - IMPROVED LOGIC
                if sprite_type == 'vine':
                    block_def['tileable'] = {'top': True, 'right': False, 'bottom': True, 'left': False}
                elif sprite_type == 'vertical':  # cactus
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
                elif sprite_type == 'log':
                    block_def['tileable'] = {'top': True, 'right': True, 'bottom': True, 'left': True}
                else:  # standard and unknown types
                    block_def['tileable'] = {'top': False, 'right': False, 'bottom': False, 'left': False}
                
                self.blocks['custom'].append(block_def)
                
                # Debug output for sprite type detection
                print(f"Block '{block_id}' detected as type '{sprite_type}' from path: {sprite_path}")
        
        # Sort custom blocks by name
        self.blocks['custom'].sort(key=lambda x: x['name'])
        
        print(f"Created {len(self.blocks['custom'])} custom blocks")
    
    def create_friendly_name(self, block_id):
        """Create a user-friendly name from block ID"""
        # Remove prefixes and clean up
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
            if part and not part.isdigit():  # Skip empty parts and numbers
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
        if self.load_sprite_file(sprite_path):
            # Create block definition
            sprite_type = self.detect_sprite_type_from_path(sprite_path)
            
            block_def = {
                'id': block_id,
                'name': block_name or self.create_friendly_name(block_id),
                'color': (200, 200, 200),
                'category': 'custom',
                'custom': True,
                'tileSet': sprite_type != 'standard',
                'tileMode': sprite_type
            }
            
            # Add to custom category
            self.blocks['custom'].append(block_def)
            return True
        
        return False
    
    def debug_sprite_info(self, block_id):
        """Print debug information about a sprite"""
        sprite = self.get_sprite(block_id)
        block = self.get_block_by_id(block_id)
        sprite_path = self.sprite_paths.get(block_id, "Unknown")
        
        print(f"\n=== DEBUG INFO: {block_id} ===")
        print(f"Sprite exists: {sprite is not None}")
        if sprite:
            print(f"Sprite size: {sprite.get_width()}x{sprite.get_height()}")
        print(f"Sprite path: {sprite_path}")
        print(f"Block definition: {block}")
        if block:
            print(f"Tile mode: {block.get('tileMode', 'standard')}")
            print(f"Tile set: {block.get('tileSet', False)}")
        print("=" * 50)
    
    def get_sprite_type_summary(self):
        """Get a summary of all sprite types detected"""
        type_counts = {}
        
        for block_id, sprite_path in self.sprite_paths.items():
            sprite_type = self.detect_sprite_type_from_path(sprite_path)
            type_counts[sprite_type] = type_counts.get(sprite_type, 0) + 1
        
        print("\n=== SPRITE TYPE SUMMARY ===")
        for sprite_type, count in sorted(type_counts.items()):
            print(f"{sprite_type}: {count} sprites")
        print("=" * 30)
