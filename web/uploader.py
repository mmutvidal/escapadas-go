import json
import boto3

from config.settings import AWS_ACCESS_KEY_ID,AWS_SECRET_ACCESS_KEY,AWS_REGION,S3_BUCKET

s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)

def upload_flights_json(data: dict, key: str):
    body = json.dumps(data, ensure_ascii=False, indent=2)
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="application/json",
        # ACL="public-read",
    )
    print(f"JSON subido a: https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}")
