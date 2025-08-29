import os
import re
from typing import Union

import jsii  # type: ignore
from aws_cdk import aws_iam  # type: ignore
from aws_cdk import IAspect  # type: ignore
from constructs import IConstruct  # type: ignore
from jsii._reference_map import _refs  # type: ignore
from jsii._utils import Singleton  # type: ignore

# from aws_cdk import Stack

REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION"))


@jsii.implements(IAspect)
class PermissionBoundaryAspect:
    """
    This aspect finds all aws_iam.Role objects in a node (ie. CDK stack) and
    sets permission boundary to the given ARN.
    """

    def __init__(
        self,
        *,
        permission_boundary: Union[aws_iam.ManagedPolicy, str],
        iam_prefix: str = "",
        iam_suffix: str = "",
    ) -> None:
        """
        :param permission_boundary: Either aws_iam.ManagedPolicy object
        or managed policy's ARN string
        """
        self.permission_boundary = permission_boundary
        self.iam_prefix = iam_prefix
        self.iam_suffix = iam_suffix

    def visit(self, construct_ref: IConstruct) -> None:
        """
        construct_ref only contains a string reference to an object. To get the actual
        object, we need to resolve it using JSII mapping.
        :param construct_ref: ObjRef object with string reference to the actual object.
        :return: None
        """
        if isinstance(construct_ref, jsii._kernel.ObjRef) and hasattr(
            construct_ref,
            "ref",
        ):
            kernel = Singleton._instances[
                jsii._kernel.Kernel
            ]  # The same object is available as: jsii.kernel
            resolve = _refs.resolve(kernel, construct_ref)
        else:
            resolve = construct_ref

        def _get_role_name(resource_path: str, length: int = 128):
            uniqueness_len = 8
            hash_value = str(hash(f"{resource_path}-{REGION}"))
            hash_value = hash_value[
                len(hash_value) - uniqueness_len : len(hash_value)  # noqa E203
            ]
            role_name = re.sub(r"\s", "", _get_resource_id(resource_path))
            role_name = role_name[
                0 : length  # noqa E203
                - uniqueness_len
                - len(self.iam_prefix)
                - len(self.iam_suffix)
            ]
            return f"{self.iam_prefix}{role_name}{hash_value}{self.iam_suffix}"

        def _get_resource_id(resource_path: str):
            return re.sub("[/:]", "-", resource_path)

        def _walk(obj):
            if isinstance(obj, aws_iam.Role):
                cfn_role = obj.node.find_child("Resource")
                policy_arn = (
                    self.permission_boundary
                    if isinstance(self.permission_boundary, str)
                    else self.permission_boundary.managed_policy_arn
                )
                cfn_role.add_property_override("PermissionsBoundary", policy_arn)
                cfn_role.add_property_override(
                    "RoleName",
                    _get_role_name(obj.node.path, 64),
                )
            elif isinstance(obj, aws_iam.Policy):
                cfn_policy = obj.node.find_child("Resource")
                cfn_policy.add_property_override(
                    "PolicyName",
                    _get_role_name(obj.node.path),
                )
            elif isinstance(obj, aws_iam.ManagedPolicy):
                cfn_policy = obj.node.find_child("Resource")
                cfn_policy.add_property_override(
                    "ManagedPolicyName",
                    _get_role_name(obj.node.path),
                )
            elif isinstance(obj, aws_iam.InstanceProfile):
                cfn_instance_profile = obj.node.find_child("Resource")
                cfn_instance_profile.add_property_override(
                    "InstanceProfileName",
                    _get_role_name(obj.node.path),
                )
            else:
                if hasattr(obj, "permissions_node"):
                    for c in obj.permissions_node.children:
                        _walk(c)
                if hasattr(obj, "node") and obj.node.children:
                    for c in obj.node.children:
                        _walk(c)

        _walk(resolve)
