# boiler
build it all...

Known issues:
1. restoring "name 'T' is not defined" will restore anything with a T in it.
2. restoring enum will make __init__ functions appear, wtf.
3. named globals arent supported and thus always get restored.

TODO:
1. get more test code and have something that deletes random lines from it. Can boil fix it?
2. add .h/.c support instead of just .py
3. if boiler knows the filetype and can parse the file, it can do a partial restore. otherwise, it must do full restore.
4. research "tree-shaking" techniques.
