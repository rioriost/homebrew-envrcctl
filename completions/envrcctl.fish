function _envrcctl_completion;
    set -l response (env _ENVRCCTL_COMPLETE=fish_complete COMP_WORDS=(commandline -cp) COMP_CWORD=(commandline -t) envrcctl);

    for completion in $response;
        set -l metadata (string split 
 $completion);

        if test $metadata[1] = "dir";
            __fish_complete_directories $metadata[2];
        else if test $metadata[1] = "file";
            __fish_complete_path $metadata[2];
        else if test $metadata[1] = "plain";
            if test $metadata[3] != "_";
                echo $metadata[2]	$metadata[3];
            else;
                echo $metadata[2];
            end;
        end;
    end;
end;

complete --no-files --command envrcctl --arguments "(_envrcctl_completion)";
