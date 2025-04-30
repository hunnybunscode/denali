package daffodil.conversion;

import java.io.ByteArrayInputStream;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.function.Consumer;

import software.amazon.awssdk.core.async.AsyncRequestBody;
import software.amazon.awssdk.core.async.BlockingInputStreamAsyncRequestBody;
import software.amazon.awssdk.services.s3.S3AsyncClient;
import software.amazon.awssdk.services.s3.model.AbortMultipartUploadRequest;
import software.amazon.awssdk.services.s3.model.CompleteMultipartUploadRequest;
import software.amazon.awssdk.services.s3.model.CompletedMultipartUpload;
import software.amazon.awssdk.services.s3.model.CompletedPart;
import software.amazon.awssdk.services.s3.model.CreateMultipartUploadRequest;
import software.amazon.awssdk.services.s3.model.CreateMultipartUploadResponse;
import software.amazon.awssdk.services.s3.model.PutObjectResponse;
import software.amazon.awssdk.services.s3.model.Tag;
import software.amazon.awssdk.services.s3.model.Tagging;
import software.amazon.awssdk.services.s3.model.UploadPartResponse;

public class S3OutputStream extends OutputStream {

  /**
   * Default chunk size is 10MB
   */
  protected static final int BUFFER_SIZE = 10000000;

  /**
   * The bucket-name on Amazon S3
   */
  private final String bucket;

  /**
   * The path (key) name within the bucket
   */
  private final String path;

  /**
   * The temporary buffer used for storing the chunks
   */
  private final byte[] buf;

  private final S3AsyncClient s3Client;
  /**
   * Collection of the etags for the parts that have been uploaded
   */
  private final List<String> etags;
  /**
   * The position in the buffer
   */
  private int position;
  /**
   * The unique id for this upload
   */
  private String uploadId;
  /**
   * indicates whether the stream is still open / valid
   */
  private boolean open;

  private final String contentType;

  private final List<Tag> tagging;

  private final Consumer<String> eTagValidator;

  /**
   * Creates a new S3 OutputStream
   *
   * @param s3Client the AmazonS3 client
   * @param bucket   name of the bucket
   * @param path     path within the bucket
   */
  public S3OutputStream(S3AsyncClient s3Client, String bucket, String path) {
    
    this(s3Client, bucket, path, null, null, null);
  }

  /**
   * Creates a new S3 OutputStream
   *
   * @param s3Client the AmazonS3 client
   * @param bucket   name of the bucket
   * @param path     path within the bucket
   * @param contentType Optional - the content type of the file will default to application/octet-stream
   */
  public S3OutputStream(S3AsyncClient s3Client, String bucket, String path, String contentType,
      List<Tag> tagging, Consumer<String> eTagValidator) {
    this.s3Client = s3Client;
    this.bucket = bucket;
    this.path = path;
    this.contentType = contentType;
    this.tagging = tagging;
    this.eTagValidator = eTagValidator;
    buf = new byte[BUFFER_SIZE];
    position = 0;
    etags = new ArrayList<>();
    open = true;
  }

  /**
   * 
   */
  public void cancel() {
    open = false;
    if (uploadId != null) {
      s3Client.abortMultipartUpload(AbortMultipartUploadRequest.builder()
          .bucket(bucket)
          .key(path)
          .uploadId(uploadId)
          .build()).join();
    }
  }

  @Override
  public void write(int b) {
    assertOpen();
    if (position >= buf.length) {
      flushBufferAndRewind();
    }
    buf[position++] = (byte) b;
  }

  /**
   * Write an array to the S3 output stream.
   *
   * @param b the byte-array to append
   */
  @Override
  public void write(byte[] b) {
    write(b, 0, b.length);
  }

  /**
   * Writes an array to the S3 Output Stream
   *
   * @param byteArray the array to write
   * @param o         the offset into the array
   * @param l         the number of bytes to write
   */
  @Override
  public void write(byte[] byteArray, int o, int l) {
    assertOpen();
    int ofs = o;
    int len = l;
    int size;
    while (len > (size = buf.length - position)) {
      System.arraycopy(byteArray, ofs, buf, position, size);
      position += size;
      flushBufferAndRewind();
      ofs += size;
      len -= size;
    }
    System.arraycopy(byteArray, ofs, buf, position, len);
    position += len;
  }

  /**
   * Flushes the buffer by uploading a part to S3.
   */
  @Override
  public synchronized void flush() {
    assertOpen();
  }

  @Override
  public void close() {
    if (open) {
      open = false;
      String eTag = "";
      if (uploadId != null) {
        if (position > 0) {
          uploadPart();
        }

        CompletedPart[] completedParts = new CompletedPart[etags.size()];
        for (int i = 0; i < etags.size(); i++) {
          completedParts[i] = CompletedPart.builder()
              .eTag(etags.get(i))
              .partNumber(i + 1)
              .build();
          eTag = etags.get(i); // Sets the last eTag
        }

        CompletedMultipartUpload completedMultipartUpload = CompletedMultipartUpload.builder()
            .parts(completedParts)
            .build();
        CompleteMultipartUploadRequest completeMultipartUploadRequest = CompleteMultipartUploadRequest.builder()
            .bucket(bucket)
            .key(path)
            .uploadId(uploadId)
            .multipartUpload(completedMultipartUpload)
            .build();
        s3Client.completeMultipartUpload(completeMultipartUploadRequest).join();
      } else {
        BlockingInputStreamAsyncRequestBody body = AsyncRequestBody.forBlockingInputStream((long) position);
        CompletableFuture<PutObjectResponse> uploadPartFuture = s3Client.putObject(r -> {
          r.bucket(bucket).key(path);
          if(contentType != null && !contentType.isEmpty()) {
            r.contentType(contentType);
          }
          if(tagging != null) {
            r.tagging(Tagging.builder().tagSet(tagging).build());
          }
        }, body);
        body.writeInputStream(new ByteArrayInputStream(buf, 0, position));
        eTag = uploadPartFuture.join().eTag();
      }
      if(eTagValidator != null) {
        eTagValidator.accept(eTag);
      }
    }
  }

  private void assertOpen() {
    if (!open) {
      throw new IllegalStateException("Closed");
    }
  }

  protected void flushBufferAndRewind() {
    if (uploadId == null) {
      CreateMultipartUploadRequest.Builder uploadRequest = CreateMultipartUploadRequest.builder()
          .bucket(bucket)
          .key(path);
      if(contentType != null) {
        uploadRequest = uploadRequest.contentType(contentType);
      }
      if(tagging != null) {
        uploadRequest = uploadRequest.tagging(Tagging.builder().tagSet(tagging).build());
      }
      CreateMultipartUploadResponse multipartUpload = s3Client.createMultipartUpload(uploadRequest.build()).join();
      uploadId = multipartUpload.uploadId();
    }
    uploadPart();
    position = 0;
  }

  protected void uploadPart() {
    BlockingInputStreamAsyncRequestBody body = AsyncRequestBody.forBlockingInputStream((long) position);
    CompletableFuture<UploadPartResponse> uploadPartFuture = s3Client.uploadPart(r -> 
      r.bucket(bucket).key(path).uploadId(uploadId).partNumber(etags.size() + 1),
      body);
    body.writeInputStream(new ByteArrayInputStream(buf, 0, position));
    etags.add(uploadPartFuture.join().eTag());
  }
}
