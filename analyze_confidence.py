#!/usr/bin/env python3
"""Analyze confidence scores from confidence_log.txt to determine optimal thresholds."""

import sys
from collections import defaultdict


def analyze_confidence_log(log_file="confidence_log.txt"):
    """Analyze confidence scores and suggest thresholds."""

    orb_scores = []
    color_scores = []
    all_scores = []
    by_map = defaultdict(list)

    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split('|')
                if len(parts) >= 7:
                    map_name = parts[1].strip()
                    confidence = int(parts[5].strip().rstrip('%'))
                    score_type = parts[6].strip()

                    all_scores.append(confidence)
                    by_map[map_name].append(confidence)

                    if score_type == 'orb':
                        orb_scores.append(confidence)
                    elif score_type == 'color':
                        color_scores.append(confidence)
    except FileNotFoundError:
        print(f"Error: {log_file} not found. Run detection first to generate logs.")
        return

    if not all_scores:
        print("No confidence data found in log file.")
        return

    def stats(scores, label):
        if not scores:
            return
        scores.sort()
        n = len(scores)
        print(f"\n{label}:")
        print(f"  Count: {n}")
        print(f"  Min: {min(scores)}%")
        print(f"  Max: {max(scores)}%")
        print(f"  Avg: {sum(scores)//n}%")
        print(f"  Median: {scores[n//2]}%")
        print(f"  P25 (25th percentile): {scores[n//4]}%")
        print(f"  P75 (75th percentile): {scores[3*n//4]}%")
        print(f"  P90 (90th percentile): {scores[9*n//10] if n >= 10 else scores[-1]}%")

    print("=" * 60)
    print("CONFIDENCE SCORE ANALYSIS")
    print("=" * 60)

    stats(all_scores, "ALL SCORES")
    stats(orb_scores, "ORB SCORES")
    stats(color_scores, "COLOR SCORES")

    print("\n" + "=" * 60)
    print("BY MAP:")
    print("=" * 60)
    for map_name, scores in sorted(by_map.items()):
        stats(scores, map_name)

    print("\n" + "=" * 60)
    print("RECOMMENDATIONS:")
    print("=" * 60)

    if all_scores:
        all_scores.sort()
        n = len(all_scores)

        # Suggest early_stop_threshold as P75-P90 (stop when we're in top 10-25%)
        early_stop = all_scores[3*n//4]  # 75th percentile

        # Suggest min_cache_confidence as median or P25 (trust if above average)
        cache_min = all_scores[n//4]  # 25th percentile

        print(f"\nSuggested Settings (based on your data):")
        print(f'  "early_stop_threshold": {early_stop}  // P75 - stop when match is in top 25%')
        print(f'  "min_cache_confidence": {cache_min}  // P25 - re-match if below bottom 25%')

        print(f"\nCurrent defaults:")
        print(f'  "early_stop_threshold": 75')
        print(f'  "min_cache_confidence": 60')

        if early_stop < 75:
            print(f"\n⚠️  Your early_stop_threshold (75) is TOO HIGH!")
            print(f"   Most matches are below 75%. Consider lowering to {early_stop}.")

        if cache_min > 60:
            print(f"\n⚠️  Your min_cache_confidence (60) is TOO LOW!")
            print(f"   Many low-quality matches. Consider raising to {cache_min}.")
        elif cache_min < 40:
            print(f"\n⚠️  Your min_cache_confidence (60) might be TOO HIGH!")
            print(f"   Most matches are good quality. Could lower to {cache_min}.")


if __name__ == "__main__":
    log_file = sys.argv[1] if len(sys.argv) > 1 else "confidence_log.txt"
    analyze_confidence_log(log_file)
