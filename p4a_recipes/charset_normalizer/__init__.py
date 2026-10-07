from pythonforandroid.recipe import PythonRecipe


class CharsetNormalizerRecipe(PythonRecipe):
    """
    GARRY V7 local python-for-android recipe for charset-normalizer.

    Builds charset-normalizer 2.1.1 from source instead of allowing
    pip/python-for-android to select an incompatible Android wheel.
    """

    version = "2.1.1"

    url = (
        "https://files.pythonhosted.org/packages/source/c/"
        "charset-normalizer/charset-normalizer-{version}.tar.gz"
    )

    site_packages_name = "charset_normalizer"


recipe = CharsetNormalizerRecipe()
