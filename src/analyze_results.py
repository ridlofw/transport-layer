#!/usr/bin/env python3
"""
Analisis Hasil Eksperimen Transport Layer IoT.
Membaca file dataset CSV di folder data/ dan menghasilkan metrik komparasi
serta visualisasi performa protokol TCP dan UDP.
"""

import argparse
import csv
import os
import statistics
from pathlib import Path

# Mapping file CSV ke nama display yang representatif
EXPERIMENT_LABELS = {
    "udp_baseline.csv": "UDP Baseline",
    "tcp_baseline.csv": "TCP Baseline",
    "udp_drop.csv": "UDP Data Loss (No Retry)",
    "udp_retry.csv": "UDP Data Loss (Retries)",
    "ack_drop.csv": "UDP ACK Loss (No Retry)",
    "ack_retry.csv": "UDP ACK Loss (Retries)",
    "udp_retry_t010.csv": "UDP Retry (Timeout 0.10s)",
    "udp_retry_t050.csv": "UDP Retry (Timeout 0.50s)",
    "tcp_headers.csv": "TCP (Packet Header Capture)",
    "udp_headers.csv": "UDP (Packet Header Capture)",
}

def load_metrics(csv_path: Path):
    """Membaca file CSV hasil eksperimen dan menghitung ringkasan metrik."""
    if not csv_path.exists():
        return None
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
    
    if not reader:
        return None

    count = len(reader)
    total_sends = sum(int(row["attempts"]) for row in reader)
    acked = sum(int(row["acknowledged"]) for row in reader)
    elapsed_ms = [float(row["elapsed_ms"]) for row in reader]

    median_lat = statistics.median(elapsed_ms)
    mean_lat = statistics.mean(elapsed_ms)
    max_lat = max(elapsed_ms)
    success_ratio = acked / count if count > 0 else 0.0
    retry_overhead = (total_sends - count) / count if count > 0 else 0.0

    return {
        "file": csv_path.name,
        "label": EXPERIMENT_LABELS.get(csv_path.name, csv_path.name),
        "count": count,
        "acked": acked,
        "sends": total_sends,
        "median_ms": median_lat,
        "mean_ms": mean_lat,
        "max_ms": max_lat,
        "success_ratio": success_ratio,
        "retry_overhead": retry_overhead,
        "raw_latencies": elapsed_ms,
    }

def print_summary_table(results: list[dict]):
    """Mencetak tabel ringkasan metrik ke terminal dalam format rapi."""
    print("=" * 105)
    print(f"{'Eksperimen / Skenario':<32} | {'Count':<5} | {'ACKed':<5} | {'Sends':<5} | {'Median(ms)':<10} | {'Max(ms)':<10} | {'Ratio':<7} | {'Overhead':<8}")
    print("-" * 105)
    for r in results:
        ratio_str = f"{r['success_ratio']:.2f}"
        overhead_str = f"{r['retry_overhead']:.2f}"
        print(f"{r['label']:<32} | {r['count']:<5} | {r['acked']:<5} | {r['sends']:<5} | {r['median_ms']:<10.3f} | {r['max_ms']:<10.3f} | {ratio_str:<7} | {overhead_str:<8}")
    print("=" * 105)

def generate_plot(results: list[dict], output_img: Path):
    """Menghasilkan grafik komparasi performa dan menyimpannya sebagai gambar."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.ticker as ticker
    except ImportError:
        print("[INFO] Matplotlib tidak terdeteksi. Lewati pembuatan grafik visual.")
        return

    # Filter skenario utama
    core_keys = [
        "udp_baseline.csv",
        "tcp_baseline.csv",
        "udp_drop.csv",
        "udp_retry.csv",
        "ack_drop.csv",
        "ack_retry.csv",
    ]
    core_results = [r for r in results if r["file"] in core_keys]
    if not core_results:
        return

    # Set aesthetic plot style
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, axes = plt.subplots(2, 2, figsize=(15, 11), dpi=300)
    fig.patch.set_facecolor("#FAFAFC")

    # Warna harmonis modern
    c_blue = "#2563EB"
    c_red = "#EF4444"
    c_teal = "#0D9488"
    c_amber = "#F59E0B"
    c_purple = "#7C3AED"

    labels_short = [
        "UDP Base",
        "TCP Base",
        "Data Drop\n(No Retry)",
        "Data Drop\n(Retries)",
        "ACK Drop\n(No Retry)",
        "ACK Drop\n(Retries)",
    ]

    # --- Plot 1: ACK Success Ratio vs Retry Overhead ---
    ax1 = axes[0, 0]
    ax1.set_facecolor("#FFFFFF")
    x = range(len(core_results))
    width = 0.35
    ratios = [r["success_ratio"] * 100 for r in core_results]
    overheads = [r["retry_overhead"] * 100 for r in core_results]

    b1 = ax1.bar([p - width/2 for p in x], ratios, width=width, label="ACK Success Ratio (%)", color=c_blue, alpha=0.85, edgecolor="#1E40AF")
    b2 = ax1.bar([p + width/2 for p in x], overheads, width=width, label="Retry Overhead (%)", color=c_amber, alpha=0.85, edgecolor="#B45309")

    ax1.set_title("Reliabilitas & Overhead Transmisi", fontsize=13, fontweight="bold", pad=12)
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(labels_short, rotation=15, ha="right", fontsize=9)
    ax1.set_ylabel("Persentase (%)", fontsize=11)
    ax1.set_ylim(0, 115)
    ax1.legend(loc="upper right", framealpha=0.9)
    ax1.grid(axis="y", linestyle="--", alpha=0.6)

    for bar in b1:
        h = bar.get_height()
        ax1.annotate(f"{h:.0f}%", xy=(bar.get_x() + bar.get_width() / 2, h), xytext=(0, 3),
                     textcoords="offset points", ha="center", va="bottom", fontsize=8, fontweight="bold")
    for bar in b2:
        h = bar.get_height()
        if h > 0:
            ax1.annotate(f"{h:.0f}%", xy=(bar.get_x() + bar.get_width() / 2, h), xytext=(0, 3),
                         textcoords="offset points", ha="center", va="bottom", fontsize=8, fontweight="bold")

    # --- Plot 2: Latensi Maksimum (Efek Timeout saat Loss) ---
    ax2 = axes[0, 1]
    ax2.set_facecolor("#FFFFFF")
    max_lats = [r["max_ms"] for r in core_results]
    bars_lat = ax2.bar(x, max_lats, color=[c_teal, c_teal, c_red, c_purple, c_red, c_purple], width=0.55, edgecolor="#374151")

    ax2.set_title("Maksimum Latensi per Rekaman (ms)", fontsize=13, fontweight="bold", pad=12)
    ax2.set_xticks(list(x))
    ax2.set_xticklabels(labels_short, rotation=15, ha="right", fontsize=9)
    ax2.set_ylabel("Waktu Selesai Maks (ms) [Skala Logaritmik]", fontsize=11)
    ax2.set_yscale("log")
    ax2.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.1f ms"))
    ax2.grid(axis="y", linestyle="--", alpha=0.6)

    for bar in bars_lat:
        h = bar.get_height()
        ax2.annotate(f"{h:.1f}ms", xy=(bar.get_x() + bar.get_width() / 2, h), xytext=(0, 3),
                     textcoords="offset points", ha="center", va="bottom", fontsize=8, fontweight="bold")

    # --- Plot 3: Pengaruh Konfigurasi Timeout pada Latensi Maksimum ---
    ax3 = axes[1, 0]
    ax3.set_facecolor("#FFFFFF")
    timeout_keys = ["udp_retry_t010.csv", "udp_retry.csv", "udp_retry_t050.csv"]
    timeout_labels = ["Timeout 0.10s", "Timeout 0.25s (Default)", "Timeout 0.50s"]
    timeout_results = [next((r for r in results if r["file"] == k), None) for k in timeout_keys]
    valid_timeouts = [r for r in timeout_results if r]

    if valid_timeouts:
        tx = range(len(valid_timeouts))
        t_maxs = [r["max_ms"] for r in valid_timeouts]
        t_meds = [r["median_ms"] for r in valid_timeouts]

        ax3.plot(tx, t_maxs, marker="o", color=c_red, linewidth=2.5, markersize=8, label="Max Latency (ms)")
        ax3.plot(tx, t_meds, marker="s", color=c_blue, linewidth=2, markersize=6, label="Median Latency (ms)")
        ax3.set_title("Sensitivitas Nilai Timeout pada UDP Retry", fontsize=13, fontweight="bold", pad=12)
        ax3.set_xticks(list(tx))
        ax3.set_xticklabels(timeout_labels, fontsize=10)
        ax3.set_ylabel("Waktu Selesai (ms)", fontsize=11)
        ax3.set_ylim(-10, max(t_maxs) * 1.15)
        ax3.legend(loc="upper left", framealpha=0.9)
        ax3.grid(True, linestyle="--", alpha=0.6)

        for i, val in enumerate(t_maxs):
            ax3.annotate(f"{val:.1f} ms", xy=(i, val), xytext=(0, 6),
                         textcoords="offset points", ha="center", va="bottom", fontsize=9, fontweight="bold", color=c_red)

    # --- Plot 4: Total Application Sends vs Acknowledged Records ---
    ax4 = axes[1, 1]
    ax4.set_facecolor("#FFFFFF")
    acked_counts = [r["acked"] for r in core_results]
    sends_counts = [r["sends"] for r in core_results]

    bx1 = ax4.bar([p - width/2 for p in x], acked_counts, width=width, label="Stored / ACKed Records", color="#10B981", alpha=0.85)
    bx2 = ax4.bar([p + width/2 for p in x], sends_counts, width=width, label="Total Application Sends", color="#6366F1", alpha=0.85)

    ax4.set_title("Perbandingan Pengiriman vs Penerimaan Sukses", fontsize=13, fontweight="bold", pad=12)
    ax4.set_xticks(list(x))
    ax4.set_xticklabels(labels_short, rotation=15, ha="right", fontsize=9)
    ax4.set_ylabel("Jumlah Paket", fontsize=11)
    ax4.set_ylim(0, 30)
    ax4.legend(loc="lower right", framealpha=0.9)
    ax4.grid(axis="y", linestyle="--", alpha=0.6)

    for bar in bx1:
        h = bar.get_height()
        ax4.annotate(f"{int(h)}", xy=(bar.get_x() + bar.get_width() / 2, h), xytext=(0, 2),
                     textcoords="offset points", ha="center", va="bottom", fontsize=8, fontweight="bold")
    for bar in bx2:
        h = bar.get_height()
        ax4.annotate(f"{int(h)}", xy=(bar.get_x() + bar.get_width() / 2, h), xytext=(0, 2),
                     textcoords="offset points", ha="center", va="bottom", fontsize=8, fontweight="bold")

    plt.suptitle("Analisis Kinerja Transport Layer: TCP vs UDP (IoT Telemetry Benchmark)", fontsize=16, fontweight="bold", y=0.98)
    plt.tight_layout(rect=[0, 0, 1, 0.95])

    output_img.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_img, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[OK] Visualisasi berhasil dibuat dan disimpan di: {output_img}")

def main():
    parser = argparse.ArgumentParser(description="Analisis Hasil Benchmark Transport Layer IoT.")
    base_dir = Path(__file__).resolve().parent.parent
    default_data_dir = base_dir / "data"
    default_img_path = base_dir / "docs" / "assets" / "benchmark_comparison.png"

    parser.add_argument("--data-dir", type=Path, default=default_data_dir, help="Direktori data CSV")
    parser.add_argument("--output-img", type=Path, default=default_img_path, help="Path gambar output grafik")
    parser.add_argument("--no-plot", action="store_true", help="Jangan generate plot grafik")
    args = parser.parse_args()

    data_dir = args.data_dir
    if not data_dir.exists():
        print(f"[ERROR] Direktori {data_dir} tidak ditemukan.")
        return

    csv_files = sorted(list(data_dir.glob("*.csv")))
    if not csv_files:
        print(f"[ERROR] Tidak ada file .csv di {data_dir}.")
        return

    results = []
    for f in csv_files:
        m = load_metrics(f)
        if m:
            results.append(m)

    # Urutkan berdasarkan urutan definisi EXPERIMENT_LABELS
    order_dict = {name: idx for idx, name in enumerate(EXPERIMENT_LABELS.keys())}
    results.sort(key=lambda item: order_dict.get(item["file"], 999))

    print("\nHASIL ANALISIS TELEMETRI TRANSPORT LAYER (IoT)")
    print_summary_table(results)

    if not args.no_plot:
        generate_plot(results, args.output_img)

if __name__ == "__main__":
    main()
