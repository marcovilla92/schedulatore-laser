#!/usr/bin/env python3
"""Clean database and uploaded files for fresh test"""
import sqlite3
import os
import shutil

def cleanup():
    print("Cleaning database and files...")
    print("="*60)

    # Connect to database
    conn = sqlite3.connect('database/scheduler.db')
    cursor = conn.cursor()

    # Delete all orders
    cursor.execute('DELETE FROM orders')
    print("[OK] Deleted all orders")

    # Delete all order_files
    cursor.execute('DELETE FROM order_files')
    print("[OK] Deleted all order files")

    # Delete all processing_steps
    cursor.execute('DELETE FROM processing_steps')
    print("[OK] Deleted all processing steps")

    # Delete all order_notifications
    cursor.execute('DELETE FROM order_notifications')
    print("[OK] Deleted all order notifications")

    # Delete all audit logs
    cursor.execute('DELETE FROM audit_log')
    print("[OK] Deleted all audit logs")

    conn.commit()
    conn.close()

    # Delete uploaded files
    uploads_dir = 'uploads'
    if os.path.exists(uploads_dir):
        for folder in ['pdfs', 'drawings']:
            folder_path = os.path.join(uploads_dir, folder)
            if os.path.exists(folder_path):
                for file in os.listdir(folder_path):
                    file_path = os.path.join(folder_path, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                print(f"[OK] Cleared {folder_path}")

    print("\n" + "="*60)
    print("CLEANUP COMPLETE:")
    print("  - All orders deleted")
    print("  - All files deleted")
    print("  - Database reset (structure maintained)")
    print("  - Users seed preserved")
    print("\nReady for clean test!")

if __name__ == '__main__':
    cleanup()
