from recsys.infrastructure.bootstrap.install_runtime import install_runtime
from recsys.infrastructure.bootstrap.settings_instance import SETTINGS
from recsys.infrastructure.bootstrap.verify_kernel import verify_kernel

BOOTSTRAP = install_runtime(SETTINGS)
verify_kernel(BOOTSTRAP)
