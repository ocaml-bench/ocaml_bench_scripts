(**** global dummy ****)

let interval_tail_rec i j =
  let rec aux acc i j =
    if i <= j
    then aux (j :: acc) i (j-1)
    else acc
  in
  aux [] i j

let foo x =
  (**** function pad ****)
  x

(**** fold_left ****)
let fold_left_while f acc l =
  let acc = ref acc in
  let l = ref l in
  let continue = ref true in
  while !continue do
    match !l with
    | [] -> continue := false
    | h :: t ->
      acc := f !acc h;
      l := t
  done;
  !acc


(**** do it ****)
let prepare_fold_left_add_float i = interval_tail_rec 0 i

let mk_fold_left_add_float f =
  fun l -> f (fun acc i -> acc +. float i) 0. l

let () =
  let xs = prepare_fold_left_add_float 1024 in 
  let test l = mk_fold_left_add_float fold_left_while l in
  for i = 1 to 200000 do
    ignore (test (xs))
  done
