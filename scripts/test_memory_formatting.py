#!/usr/bin/env python3
"""
Test script to verify memory storage formatting preserves plant/crop names.

This script tests the _format_interaction_for_storage() function to ensure
it properly emphasizes key entities like plant names, crop names, and symptoms.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.context.memory import _format_interaction_for_storage
from src.models.context_data import (
    ContextData, WeatherData, CurrentWeather, Forecast6h,
    LandRecords
)
from datetime import datetime


def test_hibiscus_question():
    """Test formatting with hibiscus plant question."""
    print("=" * 80)
    print("Test 1: Hibiscus leaves turning white")
    print("=" * 80)
    
    question = "Why are my hibiscus leaves turning white?"
    advice = "White leaves on hibiscus can indicate powdery mildew or nutrient deficiency."
    
    context = ContextData(
        weather=WeatherData(
            current=CurrentWeather(
                temperature=28.5,
                humidity=75,
                windSpeed=5.2,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                temperature=30.0,
                precipitationProbability=20,
                expectedRainfall=0.5,
                windSpeed=6.0
            )
        ),
        landRecords=LandRecords(
            landArea=2.5,
            soilType="Laterite",
            currentCrop="Hibiscus"
        )
    )
    
    formatted = _format_interaction_for_storage(question, advice, context)
    
    print("\nFormatted text:")
    print("-" * 80)
    print(formatted)
    print("-" * 80)
    
    # Check if key entities are emphasized
    assert "HIBISCUS" in formatted, "HIBISCUS should be emphasized in uppercase"
    assert "KEY ENTITIES" in formatted, "Should have KEY ENTITIES section"
    assert "PRESERVE" in formatted, "Should have PRESERVE instructions"
    
    print("\n✓ Test passed: Hibiscus is properly emphasized")


def test_maize_question():
    """Test formatting with maize crop question."""
    print("\n" + "=" * 80)
    print("Test 2: Maize leaves turning yellow")
    print("=" * 80)
    
    question = "Why are maize leaves turning yellow on laterite soil?"
    advice = "Yellow leaves on maize indicate nitrogen deficiency, common in laterite soil."
    
    context = ContextData(
        weather=WeatherData(
            current=CurrentWeather(
                temperature=32.0,
                humidity=65,
                windSpeed=8.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                temperature=34.0,
                precipitationProbability=10,
                expectedRainfall=0.0,
                windSpeed=10.0
            )
        ),
        landRecords=LandRecords(
            landArea=5.0,
            soilType="Laterite",
            currentCrop="Maize"
        )
    )
    
    formatted = _format_interaction_for_storage(question, advice, context)
    
    print("\nFormatted text:")
    print("-" * 80)
    print(formatted)
    print("-" * 80)
    
    # Check if key entities are emphasized
    assert "MAIZE" in formatted, "MAIZE should be emphasized"
    assert "KEY ENTITIES" in formatted, "Should have KEY ENTITIES section"
    assert "PRIMARY CROP" in formatted, "Should emphasize primary crop"
    
    print("\n✓ Test passed: Maize is properly emphasized")


def test_tomato_question():
    """Test formatting with tomato crop question."""
    print("\n" + "=" * 80)
    print("Test 3: Tomato plant disease")
    print("=" * 80)
    
    question = "My tomato plants have brown spots on leaves. What should I do?"
    advice = "Brown spots on tomato leaves indicate early blight. Apply fungicide."
    
    context = ContextData(
        weather=WeatherData(
            current=CurrentWeather(
                temperature=26.0,
                humidity=80,
                windSpeed=3.5,
                precipitation=2.0
            ),
            forecast6h=Forecast6h(
                temperature=28.0,
                precipitationProbability=60,
                expectedRainfall=5.0,
                windSpeed=4.0
            )
        ),
        landRecords=LandRecords(
            landArea=1.0,
            soilType="Red soil",
            currentCrop="Tomato"
        )
    )
    
    formatted = _format_interaction_for_storage(question, advice, context)
    
    print("\nFormatted text:")
    print("-" * 80)
    print(formatted)
    print("-" * 80)
    
    # Check if key entities are emphasized
    assert "TOMATO" in formatted, "TOMATO should be emphasized"
    assert "KEY ENTITIES" in formatted, "Should have KEY ENTITIES section"
    
    print("\n✓ Test passed: Tomato is properly emphasized")


def test_no_plant_name():
    """Test formatting when no specific plant name is mentioned."""
    print("\n" + "=" * 80)
    print("Test 4: Generic question without plant name")
    print("=" * 80)
    
    question = "What is the best time to apply fertilizer?"
    advice = "Apply fertilizer early morning or late evening for best results."
    
    context = ContextData(
        weather=WeatherData(
            current=CurrentWeather(
                temperature=30.0,
                humidity=70,
                windSpeed=5.0,
                precipitation=0.0
            ),
            forecast6h=Forecast6h(
                temperature=32.0,
                precipitationProbability=15,
                expectedRainfall=0.2,
                windSpeed=6.0
            )
        ),
        landRecords=LandRecords(
            landArea=3.0,
            soilType="Black soil",
            currentCrop="Cotton"
        )
    )
    
    formatted = _format_interaction_for_storage(question, advice, context)
    
    print("\nFormatted text:")
    print("-" * 80)
    print(formatted)
    print("-" * 80)
    
    # Should still have crop emphasis from land records
    assert "COTTON" in formatted, "Should emphasize crop from land records"
    assert "PRIMARY CROP" in formatted, "Should have PRIMARY CROP section"
    
    print("\n✓ Test passed: Crop from land records is emphasized")


if __name__ == "__main__":
    try:
        test_hibiscus_question()
        test_maize_question()
        test_tomato_question()
        test_no_plant_name()
        
        print("\n" + "=" * 80)
        print("ALL TESTS PASSED ✓")
        print("=" * 80)
        print("\nMemory formatting now properly emphasizes:")
        print("  • Plant names mentioned in questions (hibiscus, tomato, maize, etc.)")
        print("  • Crop names from land records")
        print("  • Explicit instructions to preserve specific details in summaries")
        print("\nThis should help Bedrock Agent preserve important details in session summaries.")
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
