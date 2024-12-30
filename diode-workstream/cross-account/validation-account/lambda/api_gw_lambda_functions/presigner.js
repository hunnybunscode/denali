'use strict';
import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import Path from "path";

const s3_client = new S3Client({});
const input_bucket = process.env["pitcher_bucket"]
const approved_file_types = [".wav", ".json", ".mp4", ".zip"]


export const handler = async (event, context) => {
  console.log("Event:", event)

  // Capture file name and file extension 
  const file = String(event["queryStringParameters"]["Key"])
  const fileExt = Path.extname(file)
  console.log("File Extension:", fileExt)

  // If the file extension is approved
  if (approved_file_types.includes(fileExt)) {
    const params = {
      'Bucket': input_bucket,
      'Key': file,
    };
    const command = new PutObjectCommand(params);
    const expiresIn = 60 * 60; // 1 hour

    // Generate URL and upload file
    const url = await getSignedUrl(s3_client, command, { expiresIn });
    console.log("URL:", url)
    try {
      const response = await fetch(url, {
        method: "PUT",
        body: event["Body"],
      })

      if (response.ok) {
        const message = "File upload succeeded"
        console.log(message)
        return {
          "statusCode": response.status,
          "body": message,
        }
      }

      // If the response is NOT okay
      const message = `File upload failed with the status code of ${response.status}`
      console.log(message)
      throw new Error(message)

    } catch (err) {
      console.log(err)
      return {
        "statusCode": 500,
        "body": err.message,
      }
    }

  } else { // If the file extension is NOT approved
    console.log("File type not accepted")
    return {
      "statusCode": 400,
      "body": "File type not accepted"
    }
  }
};
