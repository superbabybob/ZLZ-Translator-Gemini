"""Main entry point for ZLZ-translator (Gemini-version)"""
import sys

if __name__ == "__main__":
    if "--discord-bot" in sys.argv:
        from discord_app.bot import main as discord_main
        sys.exit(discord_main())
    else:
        from hotkey.app import main as hotkey_main
        sys.exit(hotkey_main())

