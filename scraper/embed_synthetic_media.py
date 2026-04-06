"""
embed_synthetic_media.py — Embed synthetic audio/video files for TunnelWatch and SiteWatch.
Run: python scraper/embed_synthetic_media.py
"""
import os, sys, time
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))

import faiss
from embedding.embed import get_embedding
from utils.helpers import load_json, save_json, get_logger

logger = get_logger(__name__)

NEW_MEDIA = [
    # TunnelWatch audio
    {
        "chunk_id": "tunnel_audio_0", "page_id": "tunnel_audio_0",
        "title": "TunnelWatch Queue Management Audio Guide",
        "content": (
            "This guide explains how to manage the wash queue in TunnelWatch. "
            "To change the wash queue order, open TunnelWatch and go to the Queue tab. "
            "Select the vehicle you want to move and drag it to the desired position. "
            "To remove a vehicle from the wash queue, select the vehicle card and tap Remove. "
            "To clear the entire wash queue, press Clear Queue and confirm. "
            "To send a vehicle to any position, use Send to Position from the vehicle menu."
        ),
        "images": [], "url": "", "media_type": "audio",
        "media_path": "assets/audio/tunnel_queue_audio.mp3",
        "system": "TunnelWatch", "topic": "Queue Management",
    },
    {
        "chunk_id": "tunnel_audio_1", "page_id": "tunnel_audio_1",
        "title": "TunnelWatch Devices Audio Guide",
        "content": (
            "This audio guide covers device management in TunnelWatch. "
            "To wait down the tunnel, go to Devices and select Wait Down. "
            "To override a device, select it from the device list and choose Override. "
            "Enter credentials if prompted and confirm the override. "
            "Always consult a supervisor before overriding critical devices."
        ),
        "images": [], "url": "", "media_type": "audio",
        "media_path": "assets/audio/tunnel_devices_audio.mp3",
        "system": "TunnelWatch", "topic": "Devices",
    },
    # TunnelWatch video
    {
        "chunk_id": "tunnel_video_0", "page_id": "tunnel_video_0",
        "title": "TunnelWatch How to Manage the Wash Queue Video",
        "content": (
            "Video walkthrough: managing the wash queue in TunnelWatch. "
            "Shows how to change queue order by dragging vehicle cards, "
            "remove a vehicle from the queue, clear the entire queue, "
            "enable or disable auto send, and send a vehicle to any queue position."
        ),
        "images": [], "url": "", "media_type": "video",
        "media_path": "assets/video/tunnel_queue_video.mp4",
        "system": "TunnelWatch", "topic": "Queue Management",
    },
    {
        "chunk_id": "tunnel_video_1", "page_id": "tunnel_video_1",
        "title": "TunnelWatch How to Manage Vehicle Retracts Video",
        "content": (
            "Video walkthrough: managing vehicle retracts in TunnelWatch. "
            "Shows how to add retracts to a vehicle, remove retracts, "
            "view assigned retracts, and replace retracts before tunnel entry."
        ),
        "images": [], "url": "", "media_type": "video",
        "media_path": "assets/video/tunnel_retracts_video.mp4",
        "system": "TunnelWatch", "topic": "Retracts",
    },
    # SiteWatch audio
    {
        "chunk_id": "sitewatch_audio_0", "page_id": "sitewatch_audio_0",
        "title": "SiteWatch General Sales Insights Audio Guide",
        "content": (
            "This guide explains how to use the SiteWatch historical general sales report. "
            "Log in to SiteWatch Insights and navigate to Historical Reports. "
            "Select General Sales Data to view revenue trends. "
            "Use the date range picker to filter by day, week, month, or custom period. "
            "Export the report to CSV or PDF using the export button."
        ),
        "images": [], "url": "", "media_type": "audio",
        "media_path": "assets/audio/sitewatch_sales_audio.mp3",
        "system": "SiteWatch", "topic": "Insights",
    },
    {
        "chunk_id": "sitewatch_audio_1", "page_id": "sitewatch_audio_1",
        "title": "SiteWatch Plan Analysis Insights Audio Guide",
        "content": (
            "This audio guide covers plan analysis reporting in SiteWatch Insights. "
            "Open the Insights dashboard and select Historical Plan Analysis. "
            "View active member counts, plan upgrades, downgrades, and cancellations. "
            "The plan churn report shows cancelled or switched plans in a period. "
            "Use this data to identify retention issues and improve membership offerings."
        ),
        "images": [], "url": "", "media_type": "audio",
        "media_path": "assets/audio/sitewatch_plans_audio.mp3",
        "system": "SiteWatch", "topic": "Insights",
    },
    # SiteWatch video
    {
        "chunk_id": "sitewatch_video_0", "page_id": "sitewatch_video_0",
        "title": "SiteWatch Historical General Sales Report Video",
        "content": (
            "Video walkthrough: accessing the SiteWatch Historical General Sales report. "
            "Shows how to log in to Insights, navigate to Historical Reports, "
            "set the date range, view sales totals and averages, and export the report."
        ),
        "images": [], "url": "", "media_type": "video",
        "media_path": "assets/video/sitewatch_sales_video.mp4",
        "system": "SiteWatch", "topic": "Insights",
    },
    {
        "chunk_id": "sitewatch_video_1", "page_id": "sitewatch_video_1",
        "title": "SiteWatch Historical Plan Analysis Report Video",
        "content": (
            "Video walkthrough: using the SiteWatch Historical Plan Analysis report. "
            "Shows how to view member plan performance, filter by site and plan type, "
            "check plan churn data, and export results for further analysis."
        ),
        "images": [], "url": "", "media_type": "video",
        "media_path": "assets/video/sitewatch_plans_video.mp4",
        "system": "SiteWatch", "topic": "Insights",
    },
]

if __name__ == "__main__":
    index_path    = os.path.join(_ROOT, "embeddings", "faiss_index.bin")
    metadata_path = os.path.join(_ROOT, "embeddings", "metadata.json")

    index    = faiss.read_index(index_path)
    metadata = load_json(metadata_path)
    logger.info("Existing: %d vectors, %d records", index.ntotal, len(metadata))

    new_vecs = []
    new_meta = []
    for i, chunk in enumerate(NEW_MEDIA):
        logger.info("[%d/%d] Embedding %s (%s)", i + 1, len(NEW_MEDIA), chunk["chunk_id"], chunk["media_type"])
        text = chunk["title"] + " — " + chunk["content"]
        vec  = get_embedding(text)
        if vec is None:
            logger.warning("  SKIPPED (embed failed)")
            continue
        new_meta.append({**chunk, "faiss_index": index.ntotal + len(new_vecs)})
        new_vecs.append(vec)
        if i < len(NEW_MEDIA) - 1:
            time.sleep(0.5)

    arr = np.array(new_vecs, dtype=np.float32)
    faiss.normalize_L2(arr)
    index.add(arr)
    faiss.write_index(index, index_path)
    metadata.extend(new_meta)
    save_json(metadata, metadata_path)
    logger.info("Done: %d vectors, %d records total", index.ntotal, len(metadata))
