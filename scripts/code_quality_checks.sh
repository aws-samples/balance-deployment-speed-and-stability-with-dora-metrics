# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

#!/bin/bash

# Run linting commands
pylint ./cdk/stacks
pylint ./cdk/lambdas/*/
pylint ./cdk/tests
pylint ./cdk/app.py


# Run security checks
bandit -r ./cdk -x ./cdk.out -s B101

pytest ./cdk/tests/unit/*.py
