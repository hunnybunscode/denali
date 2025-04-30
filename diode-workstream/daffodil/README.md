
# Daffodil Parsing

This project was built using CDK infrastructure as code, but can output the required cloudformation
templates

This project is set up like a standard Python project.  The initialization
process also creates a virtualenv within this project, stored under the `.venv`
directory.  To create the virtualenv it assumes that there is a `python3`
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
The `daffodil.yaml` parser stack will create a schema bucket, and will output the stack output key
`oschemabucket` with value being the schema bucket. This bucket will be where the daffodil schemas
should be uploaded along with the file `content-types.yaml`, which contains the mapping for the file
type to schema.  A test sample set can be found in `{daffodil}/test_resources/schemas`

## Content types
The daffodil parser uses the filename to determine which schema to use. It captures the term
in the 3rd part of the filename (3rd segment separated by `.`). For example, a file with the name
UNCLASS.USNDC.`INTERVAL`..._da_interval_1709659229.txt, it will look up the schema mapping for 
`INTERVAL`.