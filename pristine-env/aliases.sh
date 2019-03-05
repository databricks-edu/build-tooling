#@IgnoreInspection BashAddShebang

function py3dock {
  if [ -n "$DB_EDU_SHELL" ]
  then
    shell=$DB_EDU_SHELL
  else
    shell=${SHELL:-bash}
  fi
  shell=$(basename $shell)
  echo $shell

  #docker run -it --rm -w `pwd` -e HOME=$HOME -e USER=$USER -e TERM=vt100 \
  #  -v $HOME:$HOME pristine-python3 $shell
}

alias pydock3=py3dock
