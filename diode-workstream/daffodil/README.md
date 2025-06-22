# Daffodil Parsing

This project was built using CDK infrastructure as code, but can output the required cloudformation
templates

This project is set up like a standard Python project. The initialization
process also creates a virtualenv within this project, stored under the `.venv`
directory. To create the virtualenv it assumes that there is a `python3`
(or `python` for Windows) executable in your path with access to the `venv`
package. If for any reason the automatic creation of the virtualenv fails,
you can create the virtualenv manually.

## Prerequisites

- [maven](https://maven.apache.org/install.html)
- [java 11]()
- [python3](https://www.python.org/downloads/)
- [cdk](https://docs.aws.amazon.com/cdk/v2/guide/getting-started.html)

## Building

To manually create a virtualenv on MacOS and Linux:

```bash
$ python3 -m venv .venv
```

After the init process completes and the virtualenv is created, you can use the following
step to activate your virtualenv.

```bash
$ source .venv/bin/activate
```

If you are a Windows platform, you would activate the virtualenv like this:

```
% .venv\Scripts\activate.bat
```

Once the virtualenv is activated, you can install the required dependencies.

```bash
$ pip install -r requirements.txt
```

At this point you can now build the lambdas and synthesize the CloudFormation template for this code.

```bash
$ mvn clean package
```

This will build the lambda jars for both the parser and the daffodil schema preprocessor as well
as the cloudformation templates for daffodil and daffodil-roles stacks. These can be found in
`/target/dist-bin.zip`

## Deployment

Deploy in this order:

1. Upload the `parser.jar` and `precompiler.jar` in a s3 bucket
2. Deploy Cloudformation stack from `daffodil.yaml`

## Schema Management

The `daffodil.yaml` parser stack creates an S3 schema bucket (output as `SchemaBucket` in CloudFormation)
where you'll need to upload both your DFDL schemas and a `content-types.yaml` mapping file. Example schemas
and content-type mappings can be found in `{daffodil}/test_resources/schemas`.

## Content types

The daffodil parser uses the filename to determine which schema to use. It captures the term
in the 3rd part of the filename (3rd segment separated by `.`). For example, a file with the name
`UNCLASS.USNDC.INTERVAL.da_interval_1709659229.txt`, it will look up the schema mapping for
`INTERVAL`.

## Caching

The daffodil parser will cache reading in the content-types.yaml file from the schema bucket and
creating the content-types mapping every minute. This value can be overwritten with the parser lambda
environment variable `CONTENT_TYPE_CACHE_TTL_MINUTES`. Also, the retrieval of the data parser (and
compiling of the schema if the data parser hasn't been precompiled yet) from the schema bucket is
cached every 15 minutes. This value can be overwritten with the parser lambda environment variable
`DATA_PROCESSOR_CACHE_TTL_MINUTES`.
