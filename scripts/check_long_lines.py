import os, os.path

files = []
for root, dirs, fnames in os.walk('frontend/src'):
    for f in fnames:
        if f.endswith(('.js', '.css')):
            files.append(os.path.join(root, f))

count = 0
for f in sorted(files):
    with open(f, 'r', encoding='utf-8', errors='replace') as fh:
        for i, line in enumerate(fh, 1):
            stripped = line.rstrip()
            if len(stripped) > 120:
                count += 1
                print(os.path.relpath(f) + ':' + str(i) + ' (' + str(len(stripped)) + ')')
print('Total: ' + str(count))
