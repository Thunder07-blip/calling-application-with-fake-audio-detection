"""
enroll_speaker.py — CLI to enroll speakers for the Safe Call Platform
=====================================================================
Usage:
    # Enroll a speaker from an audio file
    python enroll_speaker.py --name "sajal" --audio ../real_recordinsg/sajal-intro.aac
    
    # List all enrolled speakers
    python enroll_speaker.py --list
    
    # Remove a speaker
    python enroll_speaker.py --remove "sajal"
"""

import argparse
import sys
import logging
from speaker_verify import SpeakerVerifier

logging.basicConfig(level=logging.INFO, format='%(message)s')

def main():
    parser = argparse.ArgumentParser(description="Enroll known speakers into the VoiceDetector system.")
    parser.add_argument("--name", type=str, help="Name of the speaker to enroll or remove")
    parser.add_argument("--audio", type=str, help="Path to the audio file for enrollment")
    parser.add_argument("--list", action="store_true", help="List all enrolled speakers")
    parser.add_argument("--remove", type=str, help="Remove a specific speaker by name")
    parser.add_argument("--enrollment_db", type=str, default="./models/enrolled_speakers.pkl", 
                        help="Path to save/load enrollments")
                        
    args = parser.parse_args()
    
    verifier = SpeakerVerifier(enrollment_path=args.enrollment_db)
    
    if args.list:
        enrolled = verifier.list_enrolled()
        if not enrolled:
            print("\nNo speakers currently enrolled.")
        else:
            print(f"\nCurrently Enrolled Speakers ({len(enrolled)}):")
            for name in enrolled:
                print(f"   - {name}")
        print("")
        return
        
    if args.remove:
        verifier.remove(args.remove)
        return
        
    if args.name and args.audio:
        print(f"\nEnrolling speaker '{args.name}' from {args.audio}...")
        try:
            verifier.enroll_from_file(args.name, args.audio)
            print("\nEnrollment complete! The ML agent will now recognize this voice.")
        except Exception as e:
            print(f"\nError enrolling speaker: {e}")
            sys.exit(1)
        return
        
    parser.print_help()

if __name__ == "__main__":
    main()
