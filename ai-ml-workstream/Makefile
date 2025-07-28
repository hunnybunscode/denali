.PHONY: deploy synth bootstrap clean

CONFIG_FILE ?= config/deployment_config.yaml

deploy:
	cdk deploy --context config_file=$(CONFIG_FILE)

synth:
	cdk synth --context config_file=$(CONFIG_FILE)

bootstrap:
	cdk bootstrap

clean:
	cdk destroy --context config_file=$(CONFIG_FILE)