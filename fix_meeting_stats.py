#!/usr/bin/env python3
"""
Meeting Usage Stats - Database Repair Script

This script diagnoses and repairs discrepancies between:
- LicenseUsage table (what the system thinks you used)
- Meeting table (actual meetings you created)

Run this directly: python fix_meeting_stats.py
"""

from sqlmodel import Session, select, func, create_engine
from datetime import datetime
from pathlib import Path
import sys

# Adjust these imports based on your project structure
try:
    from app.db import get_session, engine
    from app.models import Meeting, License, LicenseUsage
except ImportError:
    print("❌ Could not import models. Make sure you're running from project root.")
    print("   Try: cd /path/to/your/project && python fix_meeting_stats.py")
    sys.exit(1)


def diagnose_all_licenses(db: Session):
    """Check all licenses for discrepancies"""
    print("\n" + "="*70)
    print("🔍 DIAGNOSING ALL LICENSES")
    print("="*70 + "\n")
    
    licenses = db.exec(select(License)).all()
    
    if not licenses:
        print("⚠️  No licenses found in database")
        return []
    
    results = []
    now = datetime.utcnow()
    first_day_this_month = datetime(now.year, now.month, 1)
    
    for license in licenses:
        # Get usage record
        usage_record = db.exec(
            select(LicenseUsage).where(
                LicenseUsage.license_key == license.license_key,
                LicenseUsage.year == now.year,
                LicenseUsage.month == now.month
            )
        ).first()
        
        # Count actual meetings this month
        actual_meetings = db.exec(
            select(func.count(Meeting.id)).where(
                Meeting.license_id == license.id,
                Meeting.created_at >= first_day_this_month
            )
        ).one()
        
        # Count total meetings
        total_meetings = db.exec(
            select(func.count(Meeting.id)).where(Meeting.license_id == license.id)
        ).one()
        
        usage_says = usage_record.meetings_used if usage_record else 0
        discrepancy = actual_meetings - usage_says
        
        result = {
            'license': license,
            'license_key_preview': license.license_key[:12] + "...",
            'email': getattr(license, 'email', 'N/A'),
            'tier': license.tier,
            'usage_table_says': usage_says,
            'actual_meetings_this_month': actual_meetings,
            'total_meetings_all_time': total_meetings,
            'discrepancy': discrepancy,
            'needs_repair': discrepancy != 0
        }
        
        results.append(result)
        
        # Print result
        status = "❌ NEEDS REPAIR" if result['needs_repair'] else "✅ OK"
        print(f"{status} | {result['email'][:30]:30} | Tier: {result['tier']:10}")
        print(f"         License: {result['license_key_preview']}")
        print(f"         Usage table: {usage_says:3} | Actual: {actual_meetings:3} | Discrepancy: {discrepancy:+3}")
        print(f"         Total meetings (all time): {total_meetings}")
        print()
    
    return results


def repair_license(db: Session, license: License, actual_count: int):
    """Repair a specific license's usage count"""
    now = datetime.utcnow()
    
    usage_record = db.exec(
        select(LicenseUsage).where(
            LicenseUsage.license_key == license.license_key,
            LicenseUsage.year == now.year,
            LicenseUsage.month == now.month
        )
    ).first()
    
    old_value = usage_record.meetings_used if usage_record else 0
    
    if usage_record:
        usage_record.meetings_used = actual_count
        db.add(usage_record)
    else:
        usage_record = LicenseUsage(
            license_key=license.license_key,
            year=now.year,
            month=now.month,
            meetings_used=actual_count
        )
        db.add(usage_record)
    
    db.commit()
    
    return old_value, actual_count


def repair_all(results, db: Session):
    """Repair all licenses with discrepancies"""
    print("\n" + "="*70)
    print("🔧 REPAIRING DISCREPANCIES")
    print("="*70 + "\n")
    
    repaired_count = 0
    
    for result in results:
        if result['needs_repair']:
            old_val, new_val = repair_license(
                db, 
                result['license'], 
                result['actual_meetings_this_month']
            )
            repaired_count += 1
            print(f"✅ Repaired: {result['email']}")
            print(f"   {old_val} → {new_val} (corrected by {new_val - old_val:+d})")
            print()
    
    if repaired_count == 0:
        print("✅ No repairs needed - all licenses are accurate!")
    else:
        print(f"\n✅ Successfully repaired {repaired_count} license(s)")
    
    return repaired_count


def main():
    """Main script execution"""
    print("\n" + "="*70)
    print("📊 MEETING USAGE STATS - REPAIR TOOL")
    print("="*70)
    
    with Session(engine) as db:
        # Step 1: Diagnose
        results = diagnose_all_licenses(db)
        
        if not results:
            print("\n⚠️  No licenses to process")
            return
        
        # Count issues
        issues = sum(1 for r in results if r['needs_repair'])
        
        if issues == 0:
            print("\n" + "="*70)
            print("✅ ALL LICENSES ARE ACCURATE - NO REPAIRS NEEDED")
            print("="*70 + "\n")
            return
        
        # Step 2: Ask for confirmation
        print("\n" + "="*70)
        print(f"⚠️  Found {issues} license(s) with discrepancies")
        print("="*70 + "\n")
        
        response = input("Do you want to repair these discrepancies? (yes/no): ").strip().lower()
        
        if response in ['yes', 'y']:
            repair_all(results, db)
        else:
            print("\n❌ Repair cancelled. No changes made.")
        
        print("\n" + "="*70)
        print("🏁 DONE")
        print("="*70 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)