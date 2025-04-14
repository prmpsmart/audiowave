import site, os

site.addsitedir("../audiowave")
site.addsitedir("../../prmp_qt-master")

print(os.path.abspath("../../prmp_qt-master"))
