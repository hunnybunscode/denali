.PHONY: deploy synth bootstrap clean

CONFIG_FILE ?= config/deployment_config.yaml

deploy:
	cdk deploy --all --context config_file=$(CONFIG_FILE)

synth:
	cdk synth --all --context config_file=$(CONFIG_FILE)

bootstrap:
	cdk bootstrap

clean:
	cdk destroy --all --context config_file=$(CONFIG_FILE)