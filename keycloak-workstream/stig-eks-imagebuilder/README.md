# Welcome to EC2 Image Builder project

This is an image building project for CDK development with TypeScript.

The `cdk.json` file tells the CDK Toolkit how to execute your app.

## Useful commands

* `npm run build`   compile typescript to js
* `npm run watch`   watch for changes and compile
* `npm run test`    perform the jest unit tests
* `npx cdk deploy`  deploy this stack to your default AWS account/region
* `npx cdk diff`    compare deployed stack with current state
* `npx cdk synth`   emits the synthesized CloudFormation template

## Prerequisite

### AWS
* Amazon Inspector - Enabled


### References
* [Linux STIG hardening components](https://docs.aws.amazon.com/imagebuilder/latest/userguide/ib-stig.html#linux-os-stig)


### Troubleshoot
#### SSM Agent
References
* https://docs.aws.amazon.com/systems-manager/latest/userguide/troubleshooting-ssm-agent.html#systems-manager-ssm-agent-log-files
* https://docs.aws.amazon.com/systems-manager/latest/userguide/ssm-agent-logs.html

#### Debugging SELinux 

Check Audit logs for issues
```bash
ausearch -m AVC,USER_AVC,SELINUX_ERR,USER_SELINUX_ERR -ts recent
```

References

* https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/using_selinux/troubleshooting-problems-related-to-selinux_using-selinux#troubleshooting-problems-related-to-selinux_using-selinux
* https://docs.oracle.com/en/operating-systems/oracle-linux/9/fapolicyd/fapolicyd-Install.html#topic_i35_rbd_3zb

#### Check FA Policy

```bash
fapolicyd --debug-deny --permissive
```


To better understand how the allow and deny rules work now. In RHEL 8.6 fapolicy changed quite a bit, from one monolithic rule set to subsections, much like the rules.d/ system in the auditd application.
If you change the "debug-deny" to just "--debug" you will get that ENTIRE allow/deby chain I think you're looking for. --debug-deny just shows you the "denys" that are triggered so you can write allow rules for it.
as an example:dec=deny perm=open auid=1000 pid=27432 exe=/usr/bin/bash : path=/usr/local/example.sh

This would prompt you to write a rule something like: `perm=any exe=/usr/bin/bash : path=/usr/local/example.sh` or even `perm=any exe=/usr/bin/bash : dir=/usr/local/`

if you wanted to be a little less exacting.

The Trust rules are technically more secure than the simple access rules, but they are harder to maintain especially if your admin staff is small and your systems get updated frequently.Also, the STIGs don't require (yet) use of the trust rules and hashing, just the simple access rules, so you should be good with those. Just make sure and test these before deploying them for real, because application whitelisting will shut you down hard if you're not careful, needing a reboot to single mode to disable the service if you've gone and enabled them untested. (Then again, so will USBGuard :-D )


#### Trigger all Pipeline
```bash
aws imagebuilder list-image-pipelines | jq -r '.imagePipelineList[].arn' | xargs -n1 aws imagebuilder start-image-pipeline-execution --image-pipeline-arn
```

#### Scan for IAM Role Action
```bash
./generateIAMAction.ps1 -Enhance -TemplateFile (Get-ChildItem -File -Filter *.template.json -Path /Users/jktruong/workspace/engagements/denali/project-denali/keycloak-workstream/stig-eks-imagebuilder/denali-project-consultants-Admin.us-west-1.cdk.out | Select-Object -ExpandProperty FullName) -Since (Get-Date).AddHours(-48) -RoleArn arn:aws:iam::908027385618:role/cdk-hnb659fds-cfn-exec-role-908027385618-us-west-1 
```

Scan Build Action
```bash
./generateIAMAction.ps1 -Enhance -TemplateFile (Get-ChildItem -File -Filter *.template.json -Path /Users/jktruong/workspace/engagements/denali/project-denali/keycloak-workstream/stig-eks-imagebuilder/denali-project-consultants-Admin.us-west-1.cdk.out | Select-Object -ExpandProperty FullName) -Since (Get-Date).AddHours(-48) -RoleArn arn:aws:iam::908027385618:role/cdk-hnb659fds-cfn-exec-role-908027385618-us-west-1 
```