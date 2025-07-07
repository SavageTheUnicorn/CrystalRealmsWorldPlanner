import copy
from typing import Dict, List, Tuple, Any
from constants import Layer


class UndoRedoManager:
    """Manages undo/redo functionality for the world planner"""
    
    def __init__(self, max_history_size=50):
        self.max_history_size = max_history_size
        self.history: List[Dict] = []
        self.current_index = -1
        self.is_recording = True
        
    def save_state(self, layers: Dict[Layer, Dict[Tuple[int, int], Dict]], description: str = ""):
        """Save the current state to history"""
        if not self.is_recording:
            return
            
        # Create a deep copy of the layers
        state = {
            'layers': {},
            'description': description,
            'timestamp': None
        }
        
        # Deep copy each layer
        for layer_enum, layer_dict in layers.items():
            state['layers'][layer_enum] = {}
            for pos, block_data in layer_dict.items():
                state['layers'][layer_enum][pos] = copy.deepcopy(block_data)
        
        # Remove any states after current index (when undoing then making new changes)
        if self.current_index < len(self.history) - 1:
            self.history = self.history[:self.current_index + 1]
        
        # Add new state
        self.history.append(state)
        self.current_index = len(self.history) - 1
        
        # Limit history size
        if len(self.history) > self.max_history_size:
            self.history.pop(0)
            self.current_index -= 1
        
        print(f"Saved state: {description} (History: {len(self.history)} states)")
    
    def can_undo(self) -> bool:
        """Check if undo is possible"""
        return self.current_index > 0
    
    def can_redo(self) -> bool:
        """Check if redo is possible"""
        return self.current_index < len(self.history) - 1
    
    def undo(self) -> Dict[Layer, Dict[Tuple[int, int], Dict]] or None:
        """Undo to previous state"""
        if not self.can_undo():
            print("Cannot undo: no previous state")
            return None
        
        self.current_index -= 1
        state = self.history[self.current_index]
        
        print(f"Undoing to: {state.get('description', 'Unknown action')}")
        
        # Return a deep copy of the layers
        restored_layers = {}
        for layer_enum, layer_dict in state['layers'].items():
            restored_layers[layer_enum] = {}
            for pos, block_data in layer_dict.items():
                restored_layers[layer_enum][pos] = copy.deepcopy(block_data)
        
        return restored_layers
    
    def redo(self) -> Dict[Layer, Dict[Tuple[int, int], Dict]] or None:
        """Redo to next state"""
        if not self.can_redo():
            print("Cannot redo: no next state")
            return None
        
        self.current_index += 1
        state = self.history[self.current_index]
        
        print(f"Redoing to: {state.get('description', 'Unknown action')}")
        
        # Return a deep copy of the layers
        restored_layers = {}
        for layer_enum, layer_dict in state['layers'].items():
            restored_layers[layer_enum] = {}
            for pos, block_data in layer_dict.items():
                restored_layers[layer_enum][pos] = copy.deepcopy(block_data)
        
        return restored_layers
    
    def start_batch_operation(self):
        """Start a batch operation (disable recording until ended)"""
        self.is_recording = False
    
    def end_batch_operation(self, layers: Dict[Layer, Dict[Tuple[int, int], Dict]], description: str):
        """End a batch operation and save the final state"""
        self.is_recording = True
        self.save_state(layers, description)
    
    def clear_history(self):
        """Clear all history"""
        self.history.clear()
        self.current_index = -1
        print("Undo/Redo history cleared")
    
    def get_current_description(self) -> str:
        """Get description of current state"""
        if 0 <= self.current_index < len(self.history):
            return self.history[self.current_index].get('description', 'Unknown')
        return "Initial state"
    
    def get_undo_description(self) -> str:
        """Get description of state that would be undone to"""
        if self.can_undo():
            return self.history[self.current_index - 1].get('description', 'Unknown')
        return ""
    
    def get_redo_description(self) -> str:
        """Get description of state that would be redone to"""
        if self.can_redo():
            return self.history[self.current_index + 1].get('description', 'Unknown')
        return ""
    
    def get_history_info(self) -> str:
        """Get information about the current history state"""
        if not self.history:
            return "No history"
        
        return f"History: {self.current_index + 1}/{len(self.history)}"
