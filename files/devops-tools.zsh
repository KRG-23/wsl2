export FZF_DEFAULT_COMMAND='fd --type f --hidden --follow --exclude .git'
export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"
export FZF_ALT_C_COMMAND='fd --type d --hidden --follow --exclude .git'
export FZF_DEFAULT_OPTS='--height=80% --layout=reverse --border --preview-window=right,60%,wrap'
export FZF_CTRL_T_OPTS='--preview "bat --style=numbers --color=always --line-range=:300 {}"'
export FZF_ALT_C_OPTS='--preview "fd --max-depth 2 . {}"'
for binding in key-bindings completion; do
  [[ -r /usr/share/doc/fzf/examples/$binding.zsh ]] && source /usr/share/doc/fzf/examples/$binding.zsh
done
f() { local file; file=$(fd -t f . "${1:-.}" | fzf --preview 'bat --color=always --line-range=:200 {}') || return; micro "$file"; }
cdf() { local dir; dir=$(fd -t d . "${1:-.}" | fzf) || return; cd "$dir"; }
_search_open() {
  local editor=$1; shift
  [[ $# -gt 0 ]] || { print -u2 'Usage: o|oc <text>'; return 1; }
  local pick file line
  pick=$(rg --line-number --no-heading --smart-case -- "$*" | fzf --delimiter ':' --nth 3..) || return
  file=${pick%%:*}; line=${pick#*:}; line=${line%%:*}
  if [[ $editor == code ]]; then code -g "$file:$line"; else micro +"$line" "$file"; fi
}
o() { _search_open micro "$@"; }
oc() { _search_open code "$@"; }
unalias gco 2>/dev/null
gco() { local b; b=$(git branch --all --format='%(refname:short)' | sed 's#^remotes/##' | sort -u | fzf) || return; git checkout "$b"; }
gitw() {
  local exe='/mnt/c/Program Files/Git/cmd/git.exe'
  [[ -x $exe ]] || { print -u2 "Missing Git for Windows: $exe"; return 1; }
  "$exe" -C "$(wslpath -w "$PWD")" "$@"
}
_gacpw() { gitw add . && gitw commit -m "$*" && gitw push; }
alias gacpw='noglob _gacpw'
alias aliases=alias
