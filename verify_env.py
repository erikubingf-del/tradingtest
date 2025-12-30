import sys
from pathlib import Path
import json

def check_import(name):
    try:
        __import__(name)
        print(f"[OK] {name} installed")
        return True
    except ImportError:
        print(f"[FAIL] {name} missing")
        return False

def check_file(path):
    if Path(path).exists():
        print(f"[OK] {path} exists")
        return True
    else:
        print(f"[FAIL] {path} missing")
        return False

def main():
    print("--- Verifying Professional Env ---")
    
    # Check Libs
    libs = ['freqtrade', 'pandas', 'numpy', 'catboost', 'sklearn', 'plotly']
    all_libs = all(check_import(l) for l in libs)
    
    # Check Configs
    configs = ['config.json', 'config_private.json', 'user_data/strategies/BtcMomentumRider.py']
    all_files = all(check_file(c) for c in configs)
    
    # Check FreqAI
    try:
        with open('config.json') as f:
            c = json.load(f)
            if c.get('freqai', {}).get('enabled'):
                print("[OK] FreqAI enabled in config")
            else:
                print("[WARN] FreqAI disabled in config")
    except Exception as e:
        print(f"[FAIL] Could not read config.json: {e}")
        
    if all_libs and all_files:
        print("\nSUCCESS: Environment Ready for Pro Trading!")
    else:
        print("\nWARNING: Some components missing.")

if __name__ == "__main__":
    main()
