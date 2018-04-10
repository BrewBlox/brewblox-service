#! /usr/bin/python3

import argparse
import docker
import json
import re


def parse_args(sys_args: list=None):
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-u', '--user', help='Docker Hub user name')
    argparser.add_argument('-p', '--password', help='Docker Hub password')
    argparser.add_argument('-i', '--image', help='Dockerfile target dir. [%(default)s]', default='./docker')
    argparser.add_argument('-n', '--name', help='Image base name', required=True)
    argparser.add_argument('-t', '--tags', nargs='+', help='Tags to use when pushing image. ', default=[])
    argparser.add_argument('--no-cache', help='Don\'t use cache when building', action='store_true')
    return argparser.parse_args(sys_args)


def login(client, args):
    if args.user:
        print('==== Logging in ====')
        client.login(username=args.user, password=args.password)


def build(client, args):
    print('==== Building ====')

    # We're using the low-level API client to get a continuous stream of messages
    tag_name = args.name + ':temp'
    docker_client = docker.APIClient()

    generator = docker_client.build(
        path=args.image,
        tag=tag_name,
        rm=True,
        nocache=args.no_cache)

    while True:
        try:
            output = next(generator).rstrip()
            json_output = json.loads(output)
            if 'stream' in json_output:
                print(json_output['stream'].rstrip())
        except StopIteration:
            print('Docker image build complete.')
            break
        except ValueError:
            print(f'Error parsing output from docker image build: {output}')

    return client.images.get(tag_name)


def push(client, image, args):
    print('==== PUSHING ====')

    if not args.tags:
        print('No tags specified - doing nothing')

    for tag in args.tags:
        # Filter out illegal tag characters
        tag = re.sub('[/_:]', '-', tag)
        print(f'Pushing {args.name}:{tag}')

        image.tag(repository=args.name, tag=tag)
        logs = client.images.push(repository=args.name, tag=tag)
        print(logs)


def main(sys_args: list=None):
    args = parse_args(sys_args)
    print(args)
    client = docker.from_env()

    login(client, args)
    image = build(client, args)
    push(client, image, args)


if __name__ == '__main__':
    main()
