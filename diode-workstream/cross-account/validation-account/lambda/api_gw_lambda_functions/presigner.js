'use strict';
import {S3Client, PutObjectCommand} from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import https from "https";
import Path from "path";

const s3_client = new S3Client({});
const input_bucket=process.env["pitcher_bucket"]
const approved_file_types=[".wav", ".json", ".mp4", ".zip"]


export const handler = (event, context, callback) => {
  
    //Capture file name and file extension 
    console.log("This is the content of event:",event)
    const currFile=String(event["Key"])
    const currFile_ext=Path.extname(currFile)
    console.log(currFile_ext)
    
    //Validate extension 
    if (approved_file_types.includes(currFile_ext)){
      //specify
      var params = {
              'Bucket' : input_bucket,
              'Key' : currFile,
      };
      const command = new PutObjectCommand(params);
      const expiresIn =  60 * 60;
  
      
      //Generate URL and upload file
      async function generateurl(){
        try{
          const url = await getSignedUrl(s3_client, command, {expiresIn});
          console.log(url)
          await put(url, event["Key"]);
          console.log( "File successfully uploaded")
          callback(null, url)
        } catch (err) {
            console.log(err)
            return err
        }
      }
      generateurl();
      
      
      //Put Object Function 
      function put(url, data) {
        console.log("Made it to put function")
        console.log("URL officially passed in:", url)
        const request = https.request(url, (response) => { 
          response.on(data, (chunk) => { 
            data = data + chunk.toString(); 
          }); 
  
          response.on('end', () => { 
            const body = JSON.parse(data); 
            console.log(body); 
            callback(null, body)
          }); 
        }) 
  
        request.on('error', (error) => { 
          console.log('An error', error); 
        }); 
  
        request.end()
      }
  
    }else{
      console.log("File type not accepted")
      callback(null,"File type not accepted")
  }
};
