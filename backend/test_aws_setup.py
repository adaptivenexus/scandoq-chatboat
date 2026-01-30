import os
import boto3
import lancedb
from dotenv import load_dotenv
import sys

# Load env vars
load_dotenv()

def test_s3_connection():
    print("--- Testing S3 Connection ---")
    aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    bucket_name = os.getenv('AWS_STORAGE_BUCKET_NAME')
    region_name = os.getenv('AWS_S3_REGION_NAME')

    aws_session_token = os.getenv('AWS_SESSION_TOKEN')

    if not all([aws_access_key_id, aws_secret_access_key, bucket_name]):
        print("❌ Error: Missing AWS credentials in .env file.")
        return False

    print(f"🔹 Target Bucket: {bucket_name}")
    print(f"🔹 Region: {region_name}")

    try:
        s3 = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            region_name=region_name
        )
        
        # 1. Check if bucket exists/accessible
        print("1️⃣  Verifying bucket access...")
        s3.head_bucket(Bucket=bucket_name)
        print("✅ Bucket found and accessible.")

        # 2. Try simple write
        print("2️⃣  Testing write permissions...")
        test_filename = "connection_test.txt"
        s3.put_object(Bucket=bucket_name, Key=test_filename, Body=b"Hello S3!")
        print(f"✅ Successfully uploaded {test_filename}.")

        # 3. Clean up
        s3.delete_object(Bucket=bucket_name, Key=test_filename)
        print(f"✅ Cleaned up test file.")
        
        return True

    except Exception as e:
        print(f"❌ S3 Connection Error: {e}")
        # Try listing all buckets to see if creds work generally
        try:
            print("   (Debug) Attempting to list all buckets...")
            resp = s3.list_buckets()
            print("   ✅ Credentials are VALID. Found buckets: ", [b['Name'] for b in resp['Buckets']])
            print("   ⚠️  But access to TARGET bucket is denied. Check Bucket Policies or IAM permissions for this specific bucket.")
        except Exception as e2:
            print(f"   ❌ Could not list buckets either: {e2}")
        return False

def test_lancedb_connection():
    print("\n--- Testing LanceDB S3 Connection ---")
    bucket_name = os.getenv('AWS_STORAGE_BUCKET_NAME')
    
    if not bucket_name:
        print("❌ Skpping LanceDB test due to missing bucket name.")
        return

    uri = f"s3://{bucket_name}/vectors-test"
    print(f"🔹 Connecting to LanceDB at: {uri}")

    try:
        # Connect
        db = lancedb.connect(uri)
        print("✅ LanceDB Connected.")

        # Create dummy table
        data = [{"vector": [0.1] * 768, "id": 1, "text": "test"}]
        table_name = "test_connectivity"
        
        print("1️⃣  Creating test table...")
        db.create_table(table_name, data=data, mode="overwrite")
        print("✅ Table created.")
        
        # Check
        print(f"2️⃣  Checking tables: {db.table_names()}")
        
        # Cleanup (drop table not fully supported in all lancedb versions elegantly, but we can verify it exists)
        # Assuming we just leave it or overwrite next time.
        
        print("✅ LanceDB operations successful.")
        return True

    except Exception as e:
        print(f"❌ LanceDB Error: {e}")
        return False

if __name__ == "__main__":
    s3_ok = test_s3_connection()
    if s3_ok:
        test_lancedb_connection()
    else:
        print("\n❌ Skipping LanceDB test because S3 connection failed.")
