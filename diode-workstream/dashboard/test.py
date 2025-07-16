import boto3
import random
from datetime import datetime
import json



def lambda_handler(event, context):
    min_size_bytes = 1024
    max_size_bytes = 2048
    size = random.randint(min_size_bytes, max_size_bytes)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date = datetime.now().strftime("%Y%m%d")
    bucket = 'ar-test-bucket-418585471165'
    prefix = 'transfers'
    topics = [
        'a random sport',
        'a random country',
        'a random educational major',
        'a random university',
        'a random programming language',
        'a random state',
        'a random city',
        'a random animal',
        'a random color',
        'a random food',
        'a random movie',
        'a random book',
        'a random music genre',
        'a random hobby',
        'a random car',
        'a random company',
        'a random job',
        'a random sport',
        'a random country',
        'a random educational major',
        'a random university',
        'a random programming language',
        'a random state',
        'a random city',
        'a random animal',
        'a random color',
        'a random food',
        'a random movie',
        'a random book',
        'a random music genre',
        'a random hobby',
        'a random car',
        'a random company',
        'a random job'
    ]
    topic_choice = random.choice(topics)
    print(f"File Size: {size/1024}KB")
    print(f"Topic: {topic_choice}")

    model_id = 'us.anthropic.claude-3-7-sonnet-20250219-v1:0'
    message_role = 'user',
    message_content = f'Respond with text, size of {size} bytes, and write an article about {topic_choice}.  Put the response in as a json string, with 2 keys - the first key shoudl be "title", the 2nd key should be "content".  The Title SHould include only alphanumeric Characters, and no punctuation or special characters. Do not include a leading ```json or trailing ```. Treat it as an informaitonal article, and do not provide any extra information.'

    bedrock_client = boto3.client('bedrock-runtime')

    response = bedrock_client.converse(
        modelId=model_id,
        messages=[
            {
                "role": 'user',
                "content": [
                    {
                        'text': message_content
                    }
                ]
            }
        ]

    )
    data = response['output']['message']['content'][0]['text']
    data = json.loads(data)
    title = data['title']
    content = data['content']

    s3_client = boto3.client('s3')
    print(f"Creating File Titled: {title}")
    response = s3_client.put_object(
        Bucket=bucket,
        Key=f'{prefix}/{date}/{title.replace(" ","")}.txt',
        Body=content
    )

    print(response)