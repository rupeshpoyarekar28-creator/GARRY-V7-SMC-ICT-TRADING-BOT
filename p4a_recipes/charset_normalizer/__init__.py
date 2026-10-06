from pythonforandroid.recipe import PythonRecipe


class CharsetNormalizerRecipe(PythonRecipe):
    """
    GARRY V7 local python-for-android recipe for charset-normalizer.

    Uses charset-normalizer 2.1.1 from source instead of allowing
    pip/p4a to select an incompatible prebuilt Android wheel.
    """

    version = "2.1.1"

    url = (
        "https://files.pythonhosted.org/packages/source/c/"
        "charset-normalizer/charset-normalizer-{version}.tar.gz"
    )

    site_packages_name = "charset_normalizer"


recipe = CharsetNormalizerRecipe()
