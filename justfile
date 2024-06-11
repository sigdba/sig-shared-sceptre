test:
    build/gen_all_docs.sh
    test/generate_all.sh
    test/check_diffs.sh

accept-test-changes:
    rm -Rf test/baseline
    mv test/current test/baseline
    just test
