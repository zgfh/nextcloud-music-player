#!/usr/bin/env python3
"""
Screenshot to UI Converter Demo

This script demonstrates the AI-powered screenshot to UI code conversion functionality.
"""

import sys
import os
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def create_demo_image():
    """Create a demo image for testing"""
    try:
        from PIL import Image, ImageDraw
        
        # Create a sample UI mockup
        img = Image.new('RGB', (400, 300), color='white')
        draw = ImageDraw.Draw(img)
        
        # Header
        draw.rectangle([0, 0, 400, 60], fill='#2196F3')
        draw.text((20, 20), "My App Header", fill='white')
        
        # Navigation buttons
        draw.rectangle([20, 80, 120, 110], fill='#4CAF50')
        draw.text((40, 90), "Home", fill='white')
        
        draw.rectangle([140, 80, 240, 110], fill='#FF9800')
        draw.text((170, 90), "About", fill='white')
        
        # Content area
        draw.text((20, 130), "Welcome to our application!", fill='black')
        draw.text((20, 150), "This is a sample UI design.", fill='black')
        
        # Input form
        draw.rectangle([20, 180, 300, 210], outline='#cccccc', width=2)
        draw.text((25, 190), "Enter your name...", fill='#999999')
        
        draw.rectangle([20, 220, 120, 250], fill='#2196F3')
        draw.text((50, 230), "Submit", fill='white')
        
        # Save to temp file
        temp_path = os.path.join(tempfile.gettempdir(), "demo_ui_screenshot.png")
        img.save(temp_path)
        print(f"✅ Demo image created: {temp_path}")
        return temp_path
        
    except ImportError:
        print("⚠️ PIL not available, creating text placeholder")
        temp_path = os.path.join(tempfile.gettempdir(), "demo_screenshot.txt")
        with open(temp_path, 'w') as f:
            f.write("Demo screenshot placeholder - PIL not available")
        return temp_path

def demo_progress_callback(stage, progress, message, user_options=None):
    """Demo progress callback"""
    print(f"[{stage.upper()}] {progress:.1%}: {message}")
    
    if user_options:
        print(f"  ℹ️ User Options: {user_options}")
        # Auto-select default option for demo
        default = user_options.get('default', 'auto')
        print(f"  🤖 Auto-selecting: {default}")

def main():
    """Main demo function"""
    print("🚀 Screenshot to UI Converter Demo")
    print("=" * 50)
    
    try:
        # Import the AI processor
        from nextcloud_music_player.ai_processor import AIProcessor, ProgressCallback
        
        print("✅ AI Processor loaded successfully")
        
        # Create demo image
        image_path = create_demo_image()
        
        # Initialize processor
        processor = AIProcessor()
        
        # Create progress callback
        progress_callback = ProgressCallback(demo_progress_callback)
        
        print("\n🎯 Starting AI processing pipeline...")
        print("-" * 30)
        
        # Process for different frameworks
        frameworks = ['react', 'vue', 'html']
        
        for framework in frameworks:
            print(f"\n🔄 Processing for {framework.upper()} framework...")
            
            result = processor.process_screenshot(
                image_path,
                framework,
                progress_callback
            )
            
            if result.get('success'):
                print(f"✅ {framework.upper()} code generation successful!")
                print(f"   Components detected: {len(result.get('components', []))}")
                print(f"   Code length: {len(result.get('code', ''))} characters")
                print(f"   Processing steps: {len(result.get('steps', []))}")
                
                # Save generated code
                code = result.get('code', '')
                if code:
                    extension = processor.supported_frameworks[framework]['extension']
                    output_file = f"demo_output_{framework}{extension}"
                    
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(code)
                    
                    print(f"   💾 Code saved to: {output_file}")
                
            else:
                print(f"❌ {framework.upper()} code generation failed:")
                print(f"   Error: {result.get('error', 'Unknown error')}")
        
        # Cleanup
        processor.cleanup()
        
        print("\n" + "=" * 50)
        print("🎉 Demo completed successfully!")
        print("\nGenerated files:")
        for framework in frameworks:
            extension = processor.supported_frameworks[framework]['extension']
            output_file = f"demo_output_{framework}{extension}"
            if os.path.exists(output_file):
                print(f"   📄 {output_file}")
        
        print(f"\nDemo image: {image_path}")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're running from the project root directory")
        return 1
    
    except Exception as e:
        print(f"❌ Demo error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())